"""High-level Telegram integration logic shared by webhook + notifications.

The orchestrator + tools + approvals + audit are NOT duplicated here — Telegram
is just another transport into the same pipeline.
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log
from app.db.models import Approval, Conversation, TelegramLink, User
from app.services.ai.orchestrator import AIOrchestrator
from app.services.audit.logger import AuditLogger
from app.services.billing.exceptions import DocumentLimitExceededError, SubscriptionSuspendedError
from app.services.integrations.telegram import (
    InlineButton, TelegramDocument, TelegramMessage, build_telegram_provider,
)
from app.services.proposals import (
    claim_for_generation, create_pending, find_active,
    is_cancellation, is_confirmation, mark_cancelled, mark_completed,
)
from app.services.storage import get_storage
from app.services.storage.base import sign_local_url


def _stage(stage: str, company_id: str, **kw: Any) -> None:
    """Structured per-stage log line for the Telegram pipeline.

    Useful when uvicorn logs are the only window into a webhook failure —
    grep `[telegram]` on the log to reconstruct any single request. We
    intentionally don't ship bot tokens or webhook secrets here.
    """
    log.info("telegram.stage", stage=f"[telegram] {stage}",
             company_id=company_id, **kw)


orchestrator = AIOrchestrator()
audit = AuditLogger()

# Kinds with no client/items/total at all — _try_deterministic_propose
# below gives these their own signal check and arg-building instead of
# forcing them through the commercial (client/items/total) merge logic.
_HR_KINDS = frozenset({"hr_order", "employment_contract"})


# ── Linking ────────────────────────────────────────────────────────────────

async def create_link_token(session: AsyncSession, *, user_id: str, company_id: str) -> TelegramLink:
    token = secrets.token_urlsafe(12)
    link = TelegramLink(
        token=token, user_id=user_id, company_id=company_id,
        status="PENDING", expires_at=datetime.utcnow() + timedelta(minutes=15),
    )
    session.add(link)
    await session.flush()
    return link


async def consume_link_token(
    session: AsyncSession, *, token: str, telegram_user_id: str, telegram_username: str | None,
) -> User | None:
    link = await session.get(TelegramLink, token)
    if not link or link.status != "PENDING" or link.expires_at < datetime.utcnow():
        return None
    user = await session.get(User, link.user_id)
    if not user:
        return None
    # Detach any prior link for this telegram account.
    others = await session.scalars(
        select(User).where(User.telegram_user_id == telegram_user_id, User.id != user.id),
    )
    for o in others:
        o.telegram_user_id = None
    user.telegram_user_id = telegram_user_id
    user.telegram_username = telegram_username
    link.status = "USED"
    return user


# ── Inbound message handling ───────────────────────────────────────────────

async def handle_update(session: AsyncSession, *, company_id: str, update: dict[str, Any]) -> None:
    """Route a parsed update dict to the right handler.

    This is the SHARED top-level handler the webhook calls. It NEVER raises:
    any pipeline failure is caught, logged with full traceback, and surfaced
    back to the chat as a calm error message. Letting an exception escape
    here would return 500 to Telegram, which then retries the update — a
    poison-pill loop we explicitly avoid.
    """
    t0 = time.perf_counter()
    kind = update.get("kind")
    tg_user_id = update.get("from_user")
    chat_id = update.get("chat_id") or tg_user_id

    _stage("webhook_received", company_id, update_kind=kind, tg_user_id=tg_user_id,
            text=(update.get("text") or "")[:80],
            callback_data=update.get("data"))

    try:
        provider = await build_telegram_provider(session, company_id)
        _stage("workspace_resolved", company_id, provider=provider.name)
    except Exception:  # noqa: BLE001
        log.exception("telegram.stage.workspace_resolution_failed", company_id=company_id)
        return  # No provider → can't even reply. Drop silently.

    await audit.record(
        session, company_id=company_id, actor_type="system",
        action="telegram.message_received",
        meta={"kind": kind, "from": tg_user_id, "text": (update.get("text") or "")[:120]},
    )

    if kind == "callback_query":
        try:
            await _handle_callback(session, provider, company_id, update)
        except Exception as exc:  # noqa: BLE001
            log.exception("telegram.stage.callback_failed",
                           company_id=company_id, data=update.get("data"))
            await _safe_send(provider, chat_id,
                              f"⚠️ Не удалось обработать действие: {type(exc).__name__}")
        return

    if kind != "message":
        return

    text = (update.get("text") or "").strip()

    # /start <token> binds the Telegram account to a User row.
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            user = await consume_link_token(
                session, token=parts[1].strip(),
                telegram_user_id=tg_user_id, telegram_username=update.get("username"),
            )
            if user:
                await audit.record(session, company_id=company_id, actor_type="user",
                                   actor_id=user.id, action="telegram.linked",
                                   meta={"telegram_user_id": tg_user_id})
                _stage("user_linked", company_id, user_email=user.email)
                await _safe_send(provider, chat_id,
                    f"✅ Linked to *{user.email}*. You can now ask things like _\"show unpaid invoices\"_.")
                return
        await _safe_send(provider, chat_id,
            "Welcome to Wagwan. Open the web app → Settings → *Connect Telegram* to get a one-time link code.")
        return

    if text == "/help":
        await _safe_send(provider, chat_id, _HELP)
        return

    # All other text → AI orchestrator (same tools, same guardrails).
    user = await session.scalar(select(User).where(User.telegram_user_id == tg_user_id))
    if not user:
        _stage("user_unresolved", company_id, tg_user_id=tg_user_id)
        await _safe_send(provider, chat_id,
            "🔒 Please link your account first via web → Settings → Connect Telegram.")
        return
    _stage("user_resolved", company_id, user_id=user.id, role=user.role)

    # ── Conversation persistence ──────────────────────────────────────────
    # One Conversation row per (user, chat_id). Deterministic id lets the
    # orchestrator load history without us tracking a separate mapping
    # table — same bot answer thread = same conversation_id every time,
    # which is what makes the assistant actually remember "we're in the
    # middle of an ACT proposal" across messages.
    conv_id = await _ensure_telegram_conversation(
        session, user=user, chat_id=chat_id,
    )
    _stage("conversation_resolved", company_id, user_id=user.id,
            conversation_id=conv_id, chat_id=chat_id)

    # ── Pending proposal short-circuit ────────────────────────────────────
    # Before letting the LLM see the message, check if this user has an
    # AWAITING_CONFIRMATION proposal in this chat. The proposal store is the
    # authoritative state; LLM doesn't get a vote on "да" / "отмена" because
    # Telegram messages arrive stateless (no conversation_id) and one bad
    # reformulation would lose context.
    pending = await find_active(
        session, company_id=user.company_id, user_id=user.id,
        channel="telegram", chat_id=chat_id,
    )
    if pending:
        _stage("pending_proposal_found", company_id, user_id=user.id,
                proposal_id=pending.id, kind=pending.kind,
                conversation_id=conv_id)
        if is_cancellation(text):
            await mark_cancelled(session, proposal_id=pending.id, user_id=user.id)
            await audit.record(session, company_id=user.company_id, actor_type="user",
                                actor_id=user.id, action="proposal.cancelled",
                                resource=pending.id, meta={"via": "telegram"})
            await _safe_send(provider, chat_id, "❌ Отменено.")
            return
        if is_confirmation(text):
            await _confirm_pending_proposal(
                session, provider, user=user, pending=pending, chat_id=chat_id,
            )
            return
        # Free-form text while a proposal is pending → re-build proposal
        # with the LOCKED kind. Without this guard the user could send
        # "Клиент Никита Сумма 80000" and our auto-detector might re-trigger
        # invoice/act/etc. classification — silently switching document
        # types behind the user's back. The lock holds until cancel/confirm.
        relock_handled = await _try_deterministic_propose(
            session, provider, user=user, chat_id=chat_id, text=text,
            locked_kind=pending.kind, conversation_id=conv_id,
        )
        if relock_handled:
            return
        # If the deterministic parser couldn't find new structured data,
        # fall through to the LLM so it can answer the follow-up question
        # conversationally — but it MUST keep the locked kind (the system
        # prompt already sees the conversation history including the
        # active proposal, so it has context).

    # ── Deterministic propose short-circuit ──────────────────────────────
    # When the message clearly contains a generation request + structured
    # items, build the proposal locally and skip the LLM. The LLM has been
    # observed truncating `prompt` and collapsing multi-row item lists
    # into a single scalar `total` — the parser is deterministic, so we
    # trust it whenever it has enough signal.
    short = await _try_deterministic_propose(
        session, provider, user=user, chat_id=chat_id, text=text,
        conversation_id=conv_id,
    )
    if short:
        return

    # Orchestrator boundary — wrap so tool exceptions become a chat reply,
    # not a 500 to Telegram (which would trigger Telegram's retry-storm).
    # conversation_id is the deterministic Telegram conv id so the LLM
    # sees the chat history (previous proposal, replies, edits) and stops
    # asking "what kind of document?" on every turn.
    result: dict[str, Any] | None = None
    try:
        _stage("orchestrator_started", company_id, user_id=user.id, msg_len=len(text),
                conversation_id=conv_id,
                locked_kind=(pending.kind if pending else None))
        result = await orchestrator.handle_message(
            session, company_id=user.company_id, actor_id=user.id,
            conversation_id=conv_id, message=text, actor_role=user.role,
        )
        tool_names = [t.get("name") for t in (result.get("tool_calls") or [])]
        _stage("assistant_reply_generated", company_id, user_id=user.id,
                tools=tool_names, reply_len=len((result or {}).get("reply") or ""))
    except Exception as exc:  # noqa: BLE001
        log.exception("telegram.stage.orchestrator_failed",
                       company_id=user.company_id, user_id=user.id,
                       text_preview=text[:120])
        await audit.record(session, company_id=user.company_id, actor_type="system",
                            action="telegram.orchestrator_failed",
                            meta={"text": text[:200], "exc_type": type(exc).__name__,
                                  "exc": str(exc)[:200]})
        await _safe_send(provider, chat_id,
            "⚠️ Не удалось обработать запрос. Команда уже видит ошибку — попробуйте "
            "переформулировать или подождите немного.")
        return

    # If the LLM proposed a document, persist it so the next "да" knows what
    # to generate. Replaces any previous AWAITING proposal for this chat.
    await _persist_proposal_from_result(
        session, user=user, chat_id=chat_id, text=text, result=result,
    )

    await audit.record(session, company_id=user.company_id, actor_type="user",
                       actor_id=user.id, action="telegram.command_executed",
                       meta={"text": text[:200],
                             "tools": [t["name"] for t in result.get("tool_calls", [])]})

    reply, buttons = _format_assistant_reply(result)
    _stage("telegram_send_started", company_id, user_id=user.id,
            text_len=len(reply), button_rows=len(buttons))
    try:
        await provider.send(TelegramMessage(chat_id=chat_id, text=reply, buttons=buttons))
        _stage("telegram_send_success", company_id, user_id=user.id,
                duration_ms=int((time.perf_counter() - t0) * 1000))
    except Exception:  # noqa: BLE001
        log.exception("telegram.stage.send_failed",
                       company_id=user.company_id, chat_id=chat_id)
        return

    # If the assistant generated a real document, follow up with the PDF
    # attachment so the operator can preview/sign right in Telegram.
    pdf = _extract_generated_pdf(result)
    if pdf:
        try:
            await _send_generated_document(session, provider, chat_id=chat_id, payload=pdf)
            _stage("pdf_sent", company_id, user_id=user.id,
                    filename=pdf.get("filename"))
        except Exception:  # noqa: BLE001
            log.exception("telegram.stage.pdf_send_failed",
                           company_id=user.company_id, filename=pdf.get("filename"))


async def _safe_send(provider, chat_id: str, text: str) -> None:
    """sendMessage best-effort — logs but never raises.

    Used in error-path replies so a failing send doesn't escalate to a 500
    on the webhook endpoint. Telegram is the user's only visible surface
    here; we'd rather miss a notification than enter a retry loop.
    """
    try:
        await provider.send(TelegramMessage(chat_id=chat_id, text=text))
    except Exception:  # noqa: BLE001
        log.exception("telegram.safe_send_failed", chat_id=chat_id, text_len=len(text))


async def _confirm_pending_proposal(
    session: AsyncSession, provider, *,
    user: User, pending, chat_id: str,
) -> None:
    """Run generate_document with the stored proposal payload.

    Atomic claim prevents double-fire: a second "да" while the first is
    still GENERATING gets None back and a friendly "уже работаю" reply.
    """
    claimed = await claim_for_generation(session, proposal_id=pending.id, user_id=user.id)
    if not claimed:
        _stage("proposal_already_claimed", user.company_id,
                user_id=user.id, proposal_id=pending.id)
        await _safe_send(provider, chat_id,
            "⏳ Уже создаю документ по предыдущему запросу — подождите немного.")
        return

    payload = dict(claimed.payload or {})
    _stage("proposal_confirmed", user.company_id, user_id=user.id,
            proposal_id=claimed.id, kind=claimed.kind)
    await audit.record(session, company_id=user.company_id, actor_type="user",
                        actor_id=user.id, action="proposal.confirmed",
                        resource=claimed.id, meta={"via": "telegram", "kind": claimed.kind})

    # Short ack while we render — LibreOffice can take 3–6s.
    await _safe_send(provider, chat_id, "✅ Принято. Создаю документ…")

    # Direct pipeline call — same code path the AI uses, just with payload
    # we already validated when proposing.
    from app.services.documents.generation import GenerationPipeline
    pipe = GenerationPipeline()
    try:
        result = await pipe.generate(
            session,
            company_id=user.company_id, actor_id=user.id, actor_type="user",
            kind=claimed.kind,
            prompt=payload.get("prompt"),
            overrides={
                "client_name":      payload.get("client_name"),
                "total":            payload.get("total"),
                "currency":         payload.get("currency"),
                "vat_percent":      payload.get("vat_percent"),
                "items":            payload.get("items"),
                "item_description": payload.get("item_description"),
                "qty":              payload.get("qty"),
                "notes":            payload.get("notes"),
            },
        )
    except (SubscriptionSuspendedError, DocumentLimitExceededError) as exc:
        log.info("telegram.proposal_generation_blocked",
                  company_id=user.company_id, proposal_id=claimed.id, reason=type(exc).__name__)
        await mark_completed(session, proposal_id=claimed.id, document_id=None)
        await _safe_send(provider, chat_id, f"⚠️ {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("telegram.proposal_generation_failed",
                       company_id=user.company_id, proposal_id=claimed.id)
        await mark_completed(session, proposal_id=claimed.id, document_id=None)
        await _safe_send(provider, chat_id,
            f"⚠️ Не удалось создать документ: {type(exc).__name__}. "
            "Попробуйте ещё раз или уточните параметры.")
        return

    await mark_completed(session, proposal_id=claimed.id, document_id=result.document_id)

    # Shape a generate_document-style envelope for the existing reply +
    # PDF-attachment helpers, so the user receives the same structured card
    # they would have from the LLM path.
    fake_result = {
        "reply": "",
        "tool_calls": [{
            "name": "generate_document",
            "args": {},
            "result": {
                "document_id":    result.document_id,
                "number":         result.document_number,
                "pdf_url":        result.pdf_url,
                "primary_url":    result.primary_url,
                "approval_id":    result.approval_id,
                "approval_status": result.approval_status,
                "quality_score":  (result.quality or {}).get("score"),
                "fallback_used":  result.fallback_used,
                "card":           {"kind": result.kind},
                "message":        f"{result.document_number} — готов.",
            },
        }],
    }
    reply, buttons = _format_assistant_reply(fake_result)
    await _safe_send_with_buttons(provider, chat_id, reply, buttons)

    pdf = _extract_generated_pdf(fake_result)
    if pdf:
        try:
            await _send_generated_document(session, provider, chat_id=chat_id, payload=pdf)
            _stage("pdf_sent", user.company_id, user_id=user.id,
                    filename=pdf.get("filename"))
        except Exception:  # noqa: BLE001
            log.exception("telegram.proposal.pdf_send_failed",
                           company_id=user.company_id)


async def _safe_send_with_buttons(
    provider, chat_id: str, text: str, buttons,
) -> None:
    try:
        await provider.send(TelegramMessage(chat_id=chat_id, text=text, buttons=buttons))
    except Exception:  # noqa: BLE001
        log.exception("telegram.safe_send_buttons_failed", chat_id=chat_id)


async def _ensure_telegram_conversation(
    session: AsyncSession, *, user: User, chat_id: str,
) -> str:
    """Stable one-per-(user, chat) conversation id.

    The orchestrator's `_ensure_conversation` looks up by id; we hand it a
    deterministic key so message history accumulates instead of being
    spread across a new row per turn. The old per-turn rows are what made
    the bot "forget" what document type the user picked.
    """
    conv_id = f"tg_{user.id}_{chat_id}"[:64]
    existing = await session.get(Conversation, conv_id)
    if existing:
        return conv_id
    session.add(Conversation(
        id=conv_id, company_id=user.company_id, user_id=user.id,
        title=f"Telegram · {chat_id}",
    ))
    await session.flush()
    return conv_id


async def _try_deterministic_propose(
    session: AsyncSession, provider, *,
    user: User, chat_id: str, text: str,
    locked_kind: str | None = None,
    conversation_id: str | None = None,
) -> bool:
    """When the user types a clean generation request, build the proposal
    deterministically and skip the LLM entirely.

    Returns True when handled — caller must NOT call the orchestrator.

    Trigger requires:
      * kind — either the caller passed ``locked_kind`` (active proposal
        already chose the document type and we must respect it) OR auto-
        detected via prompt keywords + an intent verb
      * structured signal — ≥2 parsed items, OR a single explicit total,
        OR labeled client/counterparty/items extracted from a follow-up

    Deliberately conservative for the no-lock path; the lock path is
    more permissive because we ALREADY know what the user wants — they
    just sent details.
    """
    from app.services.documents.generation.intent import parse_intent
    from app.services.documents.generation.classifier import KIND_LEXICON
    from app.services.ai.tools.registry import ProposeDocumentTool, ProposeDocumentArgs

    low = (text or "").lower()
    detected_kind: str | None = locked_kind
    if detected_kind is None:
        # Was a hand-maintained 5-kind table (missing hr_order/
        # employment_contract/contract_services/contract_supply/
        # act_reconciliation entirely, so the no-AI-key fallback could
        # never even detect an HR document existed) — now the same
        # lexicon classify_kind() itself falls back to when no AI key
        # is configured, so this deterministic pre-check and the LLM
        # fallback agree on what kind of document a keyword implies.
        intent_keywords = ("создай", "создать", "сделай", "сформируй", "выстав", "оформ",
                            "сгенери", "давай", "make", "create", "issue")
        for k, words in KIND_LEXICON:
            if any(w in low for w in words):
                detected_kind = k
                break
        if not detected_kind:
            return False
        if not any(w in low for w in intent_keywords):
            return False

    spec = await parse_intent(text)
    spec.kind = detected_kind  # lock — never let parser auto-switch type
    # Trim client_name if it accidentally swallowed a trailing keyword line.
    if spec.client_name:
        cleaned = spec.client_name.split("\n", 1)[0].strip()
        for stop in ("Услуги", "Товары", "Работы", "Контрагент",
                      "услуги", "товары", "работы", "контрагент"):
            cleaned = cleaned.split(stop, 1)[0].strip().rstrip(",.;:—-")
        spec.client_name = cleaned or None

    # HR kinds have no client/items/total at all — they need their own
    # signal check and their own arg-building instead of being forced
    # through the commercial merge logic below. spec.client_name here is
    # reinterpreted as employee_name: the connector regex that catches
    # "для X"/"клиент X" also fires on "приказ для Иванова..." with no
    # way to tell it's an employee, not a customer, until we already know
    # detected_kind is an HR kind.
    if detected_kind in _HR_KINDS:
        has_signal = spec.salary is not None or bool(spec.client_name)
        if not has_signal:
            return False

        _stage("deterministic_propose", user.company_id, user_id=user.id,
                kind=detected_kind, employee=spec.client_name, salary=spec.salary,
                conversation_id=conversation_id, locked_kind=locked_kind)

        args = ProposeDocumentArgs(
            kind=detected_kind, prompt=text,
            employee_name=spec.client_name,
            salary=spec.salary,
        )
        tool = ProposeDocumentTool()
        try:
            proposal_result = await tool.run(session, user.company_id, user.id, args)
        except Exception:  # noqa: BLE001
            log.exception("telegram.deterministic_propose_failed",
                           company_id=user.company_id, user_id=user.id)
            return False

        await _persist_proposal_from_result(
            session, user=user, chat_id=chat_id, text=text,
            result={"reply": "", "tool_calls": [
                {"name": "propose_document", "args": args.model_dump(),
                 "result": proposal_result},
            ]},
            conversation_id=conversation_id,
        )

        reply, buttons = _format_assistant_reply({
            "reply": "", "tool_calls": [
                {"name": "propose_document", "args": {}, "result": proposal_result},
            ],
        })
        await _safe_send_with_buttons(provider, chat_id, reply, buttons)
        await audit.record(session, company_id=user.company_id, actor_type="user",
                           actor_id=user.id, action="telegram.deterministic_propose",
                           meta={"text": text[:200], "kind": detected_kind,
                                 "locked": bool(locked_kind),
                                 "employee": spec.client_name,
                                 "salary": spec.salary,
                                 "conversation_id": conversation_id})
        return True

    # Lock-mode is more permissive: even ONE new item is enough signal to
    # update the proposal because the user is clearly amending the active
    # one. No-lock mode keeps the original gate.
    if locked_kind:
        has_signal = bool(spec.parsed_items or spec.total or spec.client_name)
    else:
        has_signal = len(spec.parsed_items) >= 2 or bool(spec.total and spec.parsed_items)
    if not has_signal:
        return False

    _stage("deterministic_propose", user.company_id, user_id=user.id,
            kind=detected_kind, client=spec.client_name,
            items_count=len(spec.parsed_items), total=spec.total,
            conversation_id=conversation_id, locked_kind=locked_kind)

    # For lock-mode, merge with existing proposal's payload so partial
    # follow-ups ("ещё добавь упаковку — 5000") don't wipe earlier data.
    merged_items = list(spec.parsed_items)
    merged_client = spec.client_name
    merged_total = spec.total
    if locked_kind:
        prior = await find_active(
            session, company_id=user.company_id, user_id=user.id,
            channel="telegram", chat_id=chat_id,
        )
        if prior and prior.payload:
            pp = prior.payload
            merged_client = merged_client or pp.get("client_name")
            prior_items = list(pp.get("items") or [])
            if not merged_items and prior_items:
                merged_items = prior_items
            elif merged_items and prior_items:
                # Append new rows; dedupe by name to avoid silly doubles
                # when the user repeats themselves.
                seen = {it.get("name") for it in prior_items}
                merged_items = prior_items + [
                    it for it in merged_items if it.get("name") not in seen
                ]
            if merged_items:
                merged_total = sum(float(it.get("total") or 0) for it in merged_items)
            elif merged_total is None:
                merged_total = pp.get("total")

    args = ProposeDocumentArgs(
        kind=detected_kind, prompt=text,
        client_name=merged_client,
        total=merged_total if not merged_items else None,
        items=[_dict_to_item(it) for it in merged_items] if merged_items else None,
    )
    tool = ProposeDocumentTool()
    try:
        proposal_result = await tool.run(session, user.company_id, user.id, args)
    except Exception:  # noqa: BLE001
        log.exception("telegram.deterministic_propose_failed",
                       company_id=user.company_id, user_id=user.id)
        return False

    await _persist_proposal_from_result(
        session, user=user, chat_id=chat_id, text=text,
        result={"reply": "", "tool_calls": [
            {"name": "propose_document", "args": args.model_dump(),
             "result": proposal_result},
        ]},
        conversation_id=conversation_id,
    )

    reply, buttons = _format_assistant_reply({
        "reply": "", "tool_calls": [
            {"name": "propose_document", "args": {}, "result": proposal_result},
        ],
    })
    await _safe_send_with_buttons(provider, chat_id, reply, buttons)
    await audit.record(session, company_id=user.company_id, actor_type="user",
                       actor_id=user.id, action="telegram.deterministic_propose",
                       meta={"text": text[:200], "kind": detected_kind,
                             "locked": bool(locked_kind),
                             "items_count": len(merged_items),
                             "total": merged_total,
                             "client": merged_client,
                             "conversation_id": conversation_id})
    return True


def _dict_to_item(d: dict[str, Any]):
    from app.services.ai.tools.registry import DocumentLineItem
    return DocumentLineItem(
        name=d.get("name") or "Позиция",
        qty=float(d.get("qty") or 1),
        price=(float(d["price"]) if d.get("price") is not None else None),
        total=(float(d["total"]) if d.get("total") is not None else None),
    )


async def _persist_proposal_from_result(
    session: AsyncSession, *, user: User, chat_id: str, text: str,
    result: dict[str, Any] | None,
    conversation_id: str | None = None,
) -> None:
    """If the assistant returned a propose_document card, snapshot the
    proposal payload to the store so the next confirm/cancel message can
    act on it without re-querying the LLM."""
    if not result:
        return
    for tc in result.get("tool_calls") or []:
        if tc.get("name") != "propose_document":
            continue
        r = tc.get("result") or {}
        if not r.get("requires_confirmation"):
            continue
        intent = r.get("intent") or {}
        items = [
            {"name": it.get("name"), "qty": it.get("qty"),
              "price": it.get("price"), "total": it.get("total")}
            for it in (r.get("items_preview") or [])
            if it.get("name")
        ]
        payload = {
            "prompt":           text,
            "client_name":      intent.get("client_name"),
            "total":            intent.get("total"),
            "currency":         intent.get("currency"),
            "vat_percent":      intent.get("vat_percent"),
            "items":            items or None,
            "item_description": None,
            "qty":              1,
            "notes":            None,
        }
        template_id = (r.get("suggested_template") or {}).get("id")
        proposal = await create_pending(
            session, company_id=user.company_id, user_id=user.id,
            channel="telegram", chat_id=chat_id, conversation_id=conversation_id,
            kind=r.get("kind") or "arbitrary_template",
            payload=payload, template_id=template_id,
        )
        _stage("proposal_persisted", user.company_id, user_id=user.id,
                proposal_id=proposal.id, kind=proposal.kind, item_count=len(items),
                conversation_id=conversation_id,
                client_name=payload.get("client_name"),
                total=payload.get("total"),
                selected_template=(r.get("suggested_template") or {}).get("name"))
        await audit.record(session, company_id=user.company_id, actor_type="ai",
                            actor_id=user.id, action="proposal.created",
                            resource=proposal.id,
                            meta={"via": "telegram", "kind": proposal.kind,
                                  "item_count": len(items)})
        return  # one proposal per turn


async def _handle_callback(session, provider, company_id: str, update: dict[str, Any]) -> None:
    data = update.get("data") or ""
    callback_id = update.get("callback_query_id")
    chat_id = update.get("chat_id")
    tg_user_id = update.get("from_user")

    user = await session.scalar(select(User).where(User.telegram_user_id == tg_user_id))
    if not user:
        await provider.answer_callback(callback_id, "Account not linked.")
        return

    # data formats: "approve:<approval_id>", "reject:<approval_id>"
    action, _, payload = data.partition(":")
    if action in ("approve", "reject") and payload:
        approval = await session.get(Approval, payload)
        if not approval or approval.company_id != user.company_id:
            await provider.answer_callback(callback_id, "Approval not found.")
            return
        if approval.status != "PENDING":
            await provider.answer_callback(callback_id, f"Already {approval.status.lower()}.")
            return
        if user.role not in ("OWNER", "ADMIN"):
            await provider.answer_callback(callback_id, "Admins only.")
            return

        from app.services.approvals.service import ApprovalService
        approve = action == "approve"
        await ApprovalService().decide(session, approval.id, approve=approve, decided_by=user.id)
        await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                           action="telegram.approval_action",
                           meta={"approval_id": approval.id, "approve": approve})
        await provider.answer_callback(callback_id, "Approved" if approve else "Rejected")
        await provider.send(TelegramMessage(
            chat_id=chat_id,
            text=f"{'✅ Approved' if approve else '❌ Rejected'}: {approval.summary}",
        ))
        return

    await provider.answer_callback(callback_id, "Unknown action.")


# ── Reply formatting ───────────────────────────────────────────────────────

def _format_assistant_reply(result: dict[str, Any]) -> tuple[str, list[list[InlineButton]]]:
    text = (result.get("reply") or "").strip() or "Done."
    buttons: list[list[InlineButton]] = []
    for tc in result.get("tool_calls") or []:
        name = tc.get("name")
        r = tc.get("result") or {}
        if name == "create_invoice" and r.get("approval_id"):
            text = (
                f"📝 *Invoice draft created*\n"
                f"Number: `{r['number']}`\n"
                f"Total: *{r['total']} {r['currency']}*\n"
                f"Status: _{r['status']}_\n\n"
                f"Approve to send via WhatsApp/Telegram."
            )
            buttons = [[
                InlineButton(text="✅ Approve", callback_data=f"approve:{r['approval_id']}"),
                InlineButton(text="❌ Reject",  callback_data=f"reject:{r['approval_id']}"),
            ]]
            break
        if name == "propose_document" and r.get("requires_confirmation"):
            # Surface the proposal as a short summary; confirmation is via
            # the user's next text message (the LLM treats "да / создай /
            # confirm" as the trigger for generate_document).
            tpl = (r.get("suggested_template") or {}).get("name") or "(встроенный fallback)"
            intent = r.get("intent") or {}
            lines = [f"🧐 *Подтверждение — {r.get('human_kind','документ')}*"]
            if intent.get("client_name"): lines.append(f"Клиент: *{intent['client_name']}*")
            if intent.get("total") is not None:
                lines.append(f"Сумма: *{intent['total']} {intent.get('currency') or 'KZT'}*")
            if intent.get("salary") is not None:
                lines.append(f"Оклад: *{intent['salary']} {intent.get('currency') or 'KZT'}*")
            if r.get("items_count"):    lines.append(f"Позиций: *{r['items_count']}*")
            lines.append(f"Шаблон: _{tpl}_")
            # Split by reason, same distinction as the web proposal card:
            # things the system genuinely can't know vs. an existing
            # reference-data record just missing some optional details.
            missing = r.get("missing_fields") or []
            to_ask = [m for m in missing if m.get("reason") != "incomplete_reference_data"]
            incomplete = [m for m in missing if m.get("reason") == "incomplete_reference_data"]
            if to_ask:
                lines.append("⚠ Не хватает: " + ", ".join(m.get("label") or m.get("field") for m in to_ask))
            if incomplete:
                lines.append("ℹ Уточните для справочника: " +
                              ", ".join(m.get("label") or m.get("field") for m in incomplete))
            lines.append("\nОтветьте *да* / *создай* для подтверждения, или уточните детали.")
            text = "\n".join(lines)
            break
        if name == "generate_document" and r.get("document_id"):
            kind = (r.get("card") or {}).get("kind") or "document"
            number = r.get("number") or ""
            quality = r.get("quality_score")
            approval_id = r.get("approval_id")
            blocked = (r.get("approval_status") == "BLOCKED")
            fallback = r.get("fallback_used")
            head = "⛔ *Заблокировано QA*" if blocked else (
                "⚠️ *Готово (fallback)*" if fallback else "✅ *Документ готов*"
            )
            text = (
                f"{head}\n"
                f"`{number}` ({kind})"
                + (f"\nQuality *{quality}/100*" if quality is not None else "")
                + ("\nДокумент НЕ будет отправлен — исправьте проблемы и пересоздайте." if blocked else "")
            )
            if approval_id and not blocked:
                buttons = [[
                    InlineButton(text="✅ Approve", callback_data=f"approve:{approval_id}"),
                    InlineButton(text="❌ Reject",  callback_data=f"reject:{approval_id}"),
                ]]
            break
        if name == "list_invoices":
            invs = r.get("invoices", [])
            if invs:
                lines = "\n".join(f"• `{i['number']}` — *{i['total']} {i['currency']}* _{i['status']}_"
                                  for i in invs[:8])
                text = f"📑 *Invoices ({len(invs)})*\n{lines}"
    return text, buttons


def _extract_generated_pdf(result: dict[str, Any]) -> dict[str, Any] | None:
    """Return ``{storage_key, filename, caption}`` for the first finished
    document attachment that should accompany the reply, else None."""
    for tc in result.get("tool_calls") or []:
        if tc.get("name") != "generate_document":
            continue
        r = tc.get("result") or {}
        url = r.get("pdf_url") or r.get("primary_url")
        if not url:
            return None
        # Signed URLs look like /api/v1/files/<key>?sig=... — extract the key
        # so we can fetch bytes directly from storage instead of round-tripping
        # through HTTP (Telegram can't reach localhost).
        key = None
        m = url.split("/api/v1/files/", 1)
        if len(m) == 2:
            key = m[1].split("?", 1)[0]
        if not key:
            return None
        return {
            "storage_key": key,
            "filename":    f"{r.get('number') or 'document'}.pdf",
            "caption":     (r.get("message") or "")[:900],
        }
    return None


async def _send_generated_document(
    session: AsyncSession, provider, *, chat_id: str, payload: dict[str, Any],
) -> None:
    """Pull bytes from storage and upload to Telegram. We always send raw
    bytes (not a URL) because in dev the storage URL points at localhost,
    which Telegram cannot fetch."""
    try:
        storage = get_storage()
        body = storage.get(payload["storage_key"])
    except Exception as exc:  # noqa: BLE001
        log.warning("telegram.send_document.fetch_failed",
                     key=payload["storage_key"][:80], err=str(exc)[:120])
        return
    try:
        await provider.send_document(TelegramDocument(
            chat_id=chat_id,
            filename=payload["filename"],
            caption=payload["caption"],
            content=body,
        ))
    except NotImplementedError:
        # Mock provider in dev — already logged as info inside the mock.
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("telegram.send_document.upload_failed",
                     err_type=type(exc).__name__)


_HELP = (
    "*Wagwan bot* — operational assistant.\n\n"
    "Try:\n"
    "• `Create invoice for TOO ABC 450000`\n"
    "• `Show unpaid invoices`\n"
    "• `Revenue this month`\n"
    "• `Find contract with Kaspi`\n\n"
    "Approvals you receive include inline buttons. "
    "For complex changes, open the web dashboard."
)


# ── Notification fan-out ───────────────────────────────────────────────────

async def notify_user(session: AsyncSession, *, user: User, text: str,
                      buttons: list[list[InlineButton]] | None = None) -> bool:
    if not user.notify_telegram or not user.telegram_user_id:
        return False
    provider = await build_telegram_provider(session, user.company_id)
    try:
        await provider.send(TelegramMessage(chat_id=user.telegram_user_id, text=text,
                                            buttons=buttons or []))
        await audit.record(session, company_id=user.company_id, actor_type="system",
                           action="telegram.notification_sent",
                           meta={"to": user.email, "preview": text[:120]})
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("telegram.notify_failed", user=user.email, error=str(exc))
        await audit.record(session, company_id=user.company_id, actor_type="system",
                           action="telegram.notification_failed",
                           meta={"to": user.email, "error": str(exc)})
        return False


async def notify_admins(session: AsyncSession, *, company_id: str, text: str,
                        buttons: list[list[InlineButton]] | None = None,
                        event_key: str = "approval_request") -> int:
    """Honor org-level + per-user notification preferences."""
    from app.services.context.service import load_context
    ctx = await load_context(session, company_id)
    if not ctx.notifications.org_telegram_enabled:
        return 0
    if not ctx.notifications.notify_on.get(event_key, True):
        return 0
    rows = await session.scalars(
        select(User).where(
            User.company_id == company_id,
            User.role.in_(("OWNER", "ADMIN")),
            User.active == True,  # noqa: E712
        ),
    )
    sent = 0
    for u in rows:
        if await notify_user(session, user=u, text=text, buttons=buttons):
            sent += 1
    return sent
