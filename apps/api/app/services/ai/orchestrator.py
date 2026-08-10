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
    "You are Wagwan, an AI operations copilot for small businesses in Kazakhstan. "
    "You handle accounting, invoicing, document generation, OCR, and workflow operations. "
    "Speak like a calm, competent operator — not like a developer console.\n\n"
    "## Voice\n"
    "- Be brief: one or two sentences per reply unless the user asks for detail.\n"
    "- Use the user's language (Russian by default for KZ tenants).\n"
    "- Confirm what you did and what happens next. Avoid restating tool outputs verbatim — "
    "the UI renders the structured card.\n"
    "- Don't quote IDs, scores, or token-style fields unless the user asked for them.\n"
    "- When something failed or is blocked, name the cause in plain language and the next step.\n\n"
    "## Safety\n"
    "You NEVER mutate financial state directly — call tools, and any state-changing tool "
    "creates a human approval before the action takes effect.\n\n"
    "## Conversation context — ALWAYS read history before acting\n"
    "Past assistant turns in the history may contain a compact context marker:\n"
    "  [ctx: propose_document(kind=act, client_name=Никита, total=60000, proposal_id=pp_...)]\n"
    "This means YOU already made that proposal earlier in this dialogue. Treat it as the\n"
    "CURRENT pending state. Specifically:\n"
    "  • a bare confirmation («да», «ок», «подтверждаю», «создай», «yes», «confirm»)\n"
    "    means: confirm THAT proposal — call `generate_document` with the SAME kind\n"
    "    and remembered fields (client_name, total, …). Do NOT call propose_document again.\n"
    "  • a correction («исправь сумму на 70000», «клиент другой — Иван») means: amend\n"
    "    the prior proposal — call `propose_document` again with the same kind plus\n"
    "    the user's updated value(s), merging in fields you already know.\n"
    "  • a free-form fragment («Никита», «60000») after you asked a follow-up\n"
    "    question (e.g. «Для какого клиента?») means: it answers your question.\n"
    "    Merge it into the in-progress proposal context and continue.\n"
    "  • a clearly new request («покажи счета», «у тебя есть шаблоны?») cancels the\n"
    "    pending proposal flow — answer the new question; do NOT confirm or amend.\n\n"
    "## Document generation — TWO-STEP confirmation flow\n"
    "Generating a document is a confirmed operator action, never an automatic reaction "
    "to any message. Follow this exact protocol:\n\n"
    "  STEP 1 (proposal). When the user asks you to create/issue/prepare any business "
    "  document (invoice / счёт, акт, накладная, договор, доверенность, etc.), call "
    "  `propose_document` with kind + the user's prompt + any explicitly stated args "
    "  (client_name, total, currency, item_description, vat_percent). This is a "
    "  READ-ONLY preview — no document is created. The UI shows the user the chosen "
    "  template, alternatives, and missing fields. Your reply should be ONE short "
    "  sentence summarising the proposal and asking the user to review/confirm.\n\n"
    "  STEP 2 (generation). Call `generate_document` ONLY when the user has explicitly "
    "  confirmed in their next message — e.g. «да», «подтверждаю», «создай», "
    "  «подтверждаю, создай», «yes», «confirm», «давай», «ок, создавай». "
    "  Do NOT call generate_document on the FIRST turn — always propose first. "
    "  Do NOT interpret «создай ...» itself as confirmation; that's the original "
    "  request, not a confirmation of a proposal.\n\n"
    "## When NOT to call any tool\n"
    "Plain questions and discussions ('что умеет система?', 'как работает OCR?', "
    "'какой шаблон лучше?', 'почему quality 84?', 'у тебя есть шаблоны?') are "
    "conversation, not actions. Answer them in 1–2 sentences without calling any "
    "tool. Tool calls are for concrete operational actions, not for explaining "
    "yourself. In particular: a meta-question about your capabilities is NEVER a "
    "request to call propose_document.\n\n"
    "## Other tools\n"
    "`create_invoice` — record/bill an invoice in the invoicing ledger (with payment "
    "tracking). Use ONLY when the user explicitly wants ledger-level invoicing, not "
    "plain document rendering.\n"
    "`list_invoices` — query the invoice list.\n\n"
    "## After a tool returns\n"
    "Don't paste the JSON. Write one operator-style sentence: what's ready or what's "
    "being proposed for confirmation, where to find it, what's pending. The "
    "structured card in the UI already shows scores, links, and diagnostics."
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
        existed = conversation_id is not None
        cid = await self._ensure_conversation(session, company_id, actor_id, conversation_id)
        log.info(
            "conversation_loaded" if existed and cid == conversation_id else "conversation_started",
            conversation_id=cid, company_id=company_id, user_id=actor_id,
        )
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
                reply, tool_calls = await self._fallback(session, company_id, actor_id, cid, message)
        else:
            reply, tool_calls = await self._fallback(session, company_id, actor_id, cid, message)

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
                result = await self._invoke_tool(session, company_id, actor_id, cid, tc.function.name, args)
                recorded.append({"name": tc.function.name, "args": args, "result": result})
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result, default=str)})
        return "I've reached the tool-call limit; please continue.", recorded

    async def _fallback(self, session, company_id, actor_id, cid, message) -> tuple[str, list[dict]]:
        # First: if the user is plainly confirming and there's an active
        # web proposal, fire generation directly — even without an LLM key.
        # Keeps the conversational confirm-flow alive in fallback mode.
        from app.services.proposals.store import is_confirmation, is_cancellation, find_active
        if is_confirmation(message):
            active = await find_active(
                session, company_id=company_id, user_id=actor_id,
                channel="web", chat_id=cid,
            )
            if active is not None:
                payload = active.payload or {}
                args = {"kind": active.kind, "prompt": payload.get("prompt") or ""}
                for k in ("client_name", "total", "currency", "vat_percent",
                          "item_description", "items", "notes"):
                    v = payload.get(k)
                    if v not in (None, "", []):
                        args[k] = v
                result = await self._invoke_tool(
                    session, company_id, actor_id, cid, "generate_document", args,
                )
                return result.get("message") or json.dumps(result, default=str), [
                    {"name": "generate_document", "args": args, "result": result},
                ]
        if is_cancellation(message):
            active = await find_active(
                session, company_id=company_id, user_id=actor_id,
                channel="web", chat_id=cid,
            )
            if active is not None:
                from app.services.proposals.store import mark_cancelled
                ok = await mark_cancelled(session, proposal_id=active.id, user_id=actor_id)
                if ok:
                    return ("Отменено.", [])

        intent = _parse_intent(message)
        if not intent:
            return (
                "AI keys not configured — fallback mode. "
                "Try: 'Create invoice for TOO ABC for 450000 KZT' or 'Show unpaid invoices'.",
                [],
            )
        result = await self._invoke_tool(session, company_id, actor_id, cid, intent["tool"], intent["args"])
        return result.get("message") or json.dumps(result, default=str), [
            {"name": intent["tool"], "args": intent["args"], "result": result},
        ]

    async def _invoke_tool(self, session, company_id, actor_id, cid, name, args) -> dict[str, Any]:
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
        return await tool.run(session, company_id, actor_id, validated, conversation_id=cid)

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
        """Reconstruct conversation history for the LLM, INCLUDING a
        summary of any tool calls the assistant made on each turn.

        Why summarise instead of replaying tool_calls in OpenAI's strict
        format: the strict format requires every assistant turn with
        tool_calls to be followed by exactly the matching tool_call_id
        results. We don't persist tool_call_ids in the Message rows, so
        we can't reconstruct that perfectly. The compromise — embed a
        short `[ctx: name(args)→result]` line in the assistant's text
        content — keeps the LLM aware of what it already did (the bug
        being fixed is that the LLM was forgetting it just proposed a
        document and treating "да" as a new request).
        """
        from sqlalchemy import select, desc
        rows = await session.scalars(
            select(Message).where(Message.conversation_id == cid)
            .order_by(desc(Message.id)).limit(limit),
        )
        msgs = list(rows)[::-1]
        out: list[dict] = []
        for m in msgs:
            if m.role not in {"user", "assistant"}:
                continue
            content = m.content or ""
            if m.role == "assistant" and m.tool_calls:
                summaries = []
                for tc in m.tool_calls:
                    name = tc.get("name") or "?"
                    args = tc.get("args") or {}
                    res = tc.get("result") or {}
                    # Pull the most distinguishing fields per tool so the
                    # LLM can tie "да" / "исправь сумму" to a concrete prior
                    # proposal. Keep it compact — this rides inside content.
                    fields = []
                    for k in ("kind", "client_name", "total", "currency",
                              "proposal_id", "document_id", "number"):
                        v = args.get(k) if k in args else res.get(k)
                        if v not in (None, "", []):
                            fields.append(f"{k}={v}")
                    if res.get("error"):
                        fields.append(f"error={res['error']}")
                    summaries.append(f"{name}({', '.join(fields)})")
                if summaries:
                    suffix = "\n[ctx: " + "; ".join(summaries) + "]"
                    content = (content + suffix).strip()
            out.append({"role": m.role, "content": content})
        return out


_AMOUNT_RE = re.compile(r"(?P<amount>\d[\d\s.,]*)\s*(?:kzt|тг|тенге|₸|т\.?)?", re.IGNORECASE)
_CLIENT_RE = re.compile(
    r"(?:for|для|клиент(?:а|у)?|to)\s+"
    r"(?P<name>(?:TOO|ТОО|ИП|АО|TOV)\s+[\wА-Яа-яЁё][\wА-Яа-яЁё\s\-\.]*?|"
    r"[\wА-Яа-яЁё][\wА-Яа-яЁё\-\.]+(?:\s+[\wА-Яа-яЁё\-\.]+){0,2})",
    re.IGNORECASE,
)


_DOC_KIND_HINTS = [
    ("act",          ["акт"]),
    ("nakladnaya",   ["накладн", "тн ", "торг-12"]),
    ("contract",     ["контракт", "договор"]),
    ("trust_letter", ["доверенност"]),
]


# Confirmation phrases that flip the fallback parser from propose → generate.
_CONFIRM_PHRASES = (
    "да", "подтверждаю", "ок,", "ок создавай", "давай создавай",
    "yes", "confirm", "подтверждаю создай",
)


def _is_confirmation(text: str) -> bool:
    low = (text or "").strip().lower()
    return any(low == p or low.startswith(p + " ") or low.startswith(p + ",")
                 for p in _CONFIRM_PHRASES)


def _parse_intent(text: str) -> dict[str, Any] | None:
    t = text.strip(); low = t.lower()
    # Generic document generation: акт / накладная / договор / доверенность.
    # First turn → propose_document (read-only preview); only after explicit
    # confirmation in the same message does generation actually run. The LLM
    # path follows the same rule via the system prompt.
    for kind, keys in _DOC_KIND_HINTS:
        if any(k in low for k in keys):
            tool = "generate_document" if _is_confirmation(t) else "propose_document"
            return {"tool": tool, "args": {"kind": kind, "prompt": t}}
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
