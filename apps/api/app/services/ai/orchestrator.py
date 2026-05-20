"""AI orchestrator — tool-calling loop with company memory injection.

Pipeline per request:
  1. Resolve / create conversation
  2. Load CompanyMemory and prepend it to the system prompt
  3. Run OpenAI tool loop, or regex fallback if no API key
  4. Persist messages, audit
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import log
from app.db.models import Conversation, Message
from app.services.ai.tools.registry import ToolRegistry
from app.services.companies.memory import CompanyMemory
from app.services.context import ContextService
from app.services.knowledge.service import KnowledgeService

BASE_SYSTEM_PROMPT = (
    "You are Buchuchet, an AI backoffice assistant for SMB businesses. "
    "You help with accounting, invoices, documents, reports, and integrations. "
    "You NEVER mutate financial state directly — call tools, and any state-changing tool "
    "creates a human approval before the action takes effect. Be concise; use the user's language."
)

MAX_TOOL_TURNS = 4


class AIOrchestrator:
    def __init__(self) -> None:
        self.tools = ToolRegistry.default()
        self.memory = CompanyMemory()
        self.context = ContextService()
        self.knowledge = KnowledgeService()

    async def handle_message(
        self, session: AsyncSession, *, company_id: str, actor_id: str,
        conversation_id: str | None, message: str, actor_role: str = "MEMBER",
    ) -> dict[str, Any]:
        self._actor_role = actor_role
        cid = await self._ensure_conversation(session, company_id, actor_id, conversation_id)
        session.add(Message(conversation_id=cid, role="user", content=message))

        # Typed business context drives prompt + downstream tool behavior.
        ctx = await self.context.load(session, company_id)
        kb_hits = await self.knowledge.retrieve(session, company_id=company_id, query=message, limit=3)
        system_prompt = BASE_SYSTEM_PROMPT + "\n\n" + ctx.to_prompt_block()
        if kb_hits:
            system_prompt += "\n## Relevant knowledge\n" + "\n".join(
                f"- *{h['title']}*: {h['snippet']}" for h in kb_hits
            ) + "\n"
        # Audit which context keys were loaded, for observability.
        from app.services.audit.logger import AuditLogger
        await AuditLogger().record(
            session, company_id=company_id, actor_type="ai", actor_id=actor_id,
            action="ai.context_loaded",
            meta={"sections": ["company", "accounting", "branding", "approvals",
                               "notifications", "integrations"],
                  "knowledge_hits": [h["id"] for h in kb_hits]},
        )

        if settings.openai_api_key:
            try:
                reply, tool_calls = await self._openai_loop(
                    session, company_id, actor_id, cid, message, system_prompt,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("openai_failure", error=str(exc))
                reply, tool_calls = await self._fallback(session, company_id, actor_id, message)
        else:
            reply, tool_calls = await self._fallback(session, company_id, actor_id, message)

        session.add(Message(conversation_id=cid, role="assistant", content=reply, tool_calls=tool_calls or None))
        return {"conversation_id": cid, "reply": reply, "tool_calls": tool_calls}

    async def _openai_loop(self, session, company_id, actor_id, cid, message, system_prompt) -> tuple[str, list[dict]]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        history = await self._history_for_llm(session, cid)
        msgs: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": message},
        ]
        recorded: list[dict] = []
        for _ in range(MAX_TOOL_TURNS):
            resp = await client.chat.completions.create(
                model=settings.ai_default_model, messages=msgs,
                tools=self.tools.openai_schema(), tool_choice="auto",
            )
            choice = resp.choices[0].message
            if not choice.tool_calls:
                return (choice.content or "").strip(), recorded
            msgs.append({
                "role": "assistant", "content": choice.content,
                "tool_calls": [tc.model_dump() for tc in choice.tool_calls],
            })
            for tc in choice.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = await self._invoke_tool(session, company_id, actor_id, tc.function.name, args)
                recorded.append({"name": tc.function.name, "args": args, "result": result})
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)})
        return "I've reached the tool-call limit; please continue.", recorded

    async def _fallback(self, session, company_id, actor_id, message) -> tuple[str, list[dict]]:
        intent = _parse_intent(message)
        if not intent:
            return (
                "AI keys not configured — fallback mode. "
                "Try: 'Create invoice for TOO ABC for 450000 KZT' or 'Show unpaid invoices'.",
                [],
            )
        result = await self._invoke_tool(session, company_id, actor_id, intent["tool"], intent["args"])
        return result.get("message") or json.dumps(result, default=str), [
            {"name": intent["tool"], "args": intent["args"], "result": result},
        ]

    async def _invoke_tool(self, session, company_id, actor_id, name, args) -> dict[str, Any]:
        from app.services.ai.tools.registry import ToolDenied
        from app.services.audit.logger import AuditLogger
        audit = AuditLogger()
        tool = self.tools.get(name)
        try:
            tool.authorize(role=getattr(self, "_actor_role", "MEMBER"))
        except ToolDenied as exc:
            await audit.record(
                session, company_id=company_id, actor_type="ai", actor_id=actor_id,
                action="ai.tool_denied", meta={"tool": name, "reason": str(exc)},
            )
            return {"error": "permission_denied", "message": str(exc)}
        try:
            validated = tool.args_model.model_validate(args)
        except Exception as exc:  # noqa: BLE001
            return {"error": "invalid_args", "message": str(exc)}
        await audit.record(
            session, company_id=company_id, actor_type="ai", actor_id=actor_id,
            action="ai.tool_invoked", meta={"tool": name, "danger": tool.danger, "args": args},
        )
        return await tool.run(session, company_id, actor_id, validated)

    async def _ensure_conversation(self, session, company_id, actor_id, conversation_id) -> str:
        if conversation_id:
            existing = await session.get(Conversation, conversation_id)
            if existing and existing.company_id == company_id:
                return conversation_id
        cid = f"conv_{uuid.uuid4().hex[:10]}"
        session.add(Conversation(id=cid, company_id=company_id, user_id=actor_id))
        await session.flush()
        return cid

    async def _history_for_llm(self, session, cid: str, limit: int = 12) -> list[dict]:
        from sqlalchemy import select, desc
        rows = await session.scalars(
            select(Message).where(Message.conversation_id == cid)
            .order_by(desc(Message.id)).limit(limit),
        )
        msgs = list(rows)[::-1]
        return [{"role": m.role, "content": m.content} for m in msgs if m.role in {"user", "assistant"}]


_AMOUNT_RE = re.compile(r"(?P<amount>\d[\d\s.,]*)\s*(?:kzt|тг|тенге|₸|т\.?)?", re.IGNORECASE)
_CLIENT_RE = re.compile(
    r"(?:for|для|клиент(?:а|у)?|to)\s+"
    r"(?P<name>(?:TOO|ТОО|ИП|АО|TOV)\s+[\wА-Яа-яЁё][\wА-Яа-яЁё\s\-\.]*?|"
    r"[\wА-Яа-яЁё][\wА-Яа-яЁё\-\.]+(?:\s+[\wА-Яа-яЁё\-\.]+){0,2})",
    re.IGNORECASE,
)


def _parse_intent(text: str) -> dict[str, Any] | None:
    t = text.strip(); low = t.lower()
    if any(k in low for k in ("invoice", "счет", "счёт", "выстав", "bill")):
        if any(k in low for k in ("create", "make", "issue", "выстав", "сдела", "созда")):
            client = None
            if m := _CLIENT_RE.search(t):
                client = m.group("name").strip().rstrip(".,")
                client = re.sub(r"\s+(на|за|for|на сумму|amount).*$", "", client, flags=re.IGNORECASE).strip()
            amount = None
            if m := _AMOUNT_RE.search(re.sub(r"^.*?(?:for|на|сумма|amount)", "", t, flags=re.IGNORECASE) or t):
                amount = float(m.group("amount").replace(" ", "").replace(",", ".").rstrip("."))
            if client and amount:
                return {"tool": "create_invoice", "args": {
                    "client_name": client,
                    "items": [{"name": "Services", "qty": 1, "price": amount}],
                }}
        if any(k in low for k in ("unpaid", "overdue", "list", "show", "какие", "покажи", "просрочен")):
            status = "OVERDUE" if "overdue" in low or "просрочен" in low else None
            return {"tool": "list_invoices", "args": {"status": status}}
    return None
