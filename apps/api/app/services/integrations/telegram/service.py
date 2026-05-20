"""High-level Telegram integration logic shared by webhook + notifications.

The orchestrator + tools + approvals + audit are NOT duplicated here — Telegram
is just another transport into the same pipeline.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log
from app.db.models import Approval, TelegramLink, User
from app.services.ai.orchestrator import AIOrchestrator
from app.services.audit.logger import AuditLogger
from app.services.integrations.telegram import (
    InlineButton, TelegramMessage, build_telegram_provider,
)


orchestrator = AIOrchestrator()
audit = AuditLogger()


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
    """Route a parsed update dict to the right handler."""
    provider = await build_telegram_provider(session, company_id)
    kind = update.get("kind")

    await audit.record(
        session, company_id=company_id, actor_type="system",
        action="telegram.message_received",
        meta={"kind": kind, "from": update.get("from_user"), "text": (update.get("text") or "")[:120]},
    )

    if kind == "callback_query":
        await _handle_callback(session, provider, company_id, update)
        return

    if kind != "message":
        return

    text = (update.get("text") or "").strip()
    chat_id = update.get("chat_id") or update.get("from_user")
    tg_user_id = update.get("from_user")

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
                await provider.send(TelegramMessage(chat_id=chat_id,
                    text=f"✅ Linked to *{user.email}*. You can now ask things like _\"show unpaid invoices\"_."))
                return
        await provider.send(TelegramMessage(chat_id=chat_id,
            text="Welcome to Buchuchet. Open the web app → Settings → *Connect Telegram* to get a one-time link code."))
        return

    if text == "/help":
        await provider.send(TelegramMessage(chat_id=chat_id, text=_HELP))
        return

    # All other text → AI orchestrator (same tools, same guardrails).
    user = await session.scalar(select(User).where(User.telegram_user_id == tg_user_id))
    if not user:
        await provider.send(TelegramMessage(chat_id=chat_id,
            text="🔒 Please link your account first via web → Settings → Connect Telegram."))
        return

    result = await orchestrator.handle_message(
        session, company_id=user.company_id, actor_id=user.id,
        conversation_id=None, message=text, actor_role=user.role,
    )
    await audit.record(session, company_id=user.company_id, actor_type="user",
                       actor_id=user.id, action="telegram.command_executed",
                       meta={"text": text[:200], "tools": [t["name"] for t in result.get("tool_calls", [])]})

    # Pretty-print one tool result if it created an approval.
    reply, buttons = _format_assistant_reply(result)
    await provider.send(TelegramMessage(chat_id=chat_id, text=reply, buttons=buttons))


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
        if tc.get("name") == "create_invoice" and tc.get("result", {}).get("approval_id"):
            r = tc["result"]
            text = (
                f"📝 *Invoice draft created*\n"
                f"Number: `{r['number']}`\n"
                f"Total: *{r['total']} {r['currency']}*\n"
                f"Status: _{r['status']}_\n\n"
                f"Approve to send via WhatsApp/Telegram."
            )
            buttons = [[
                InlineButton(text="✅ Approve",          callback_data=f"approve:{r['approval_id']}"),
                InlineButton(text="❌ Reject",           callback_data=f"reject:{r['approval_id']}"),
            ]]
            break
        if tc.get("name") == "list_invoices":
            invs = (tc.get("result") or {}).get("invoices", [])
            if invs:
                lines = "\n".join(f"• `{i['number']}` — *{i['total']} {i['currency']}* _{i['status']}_"
                                  for i in invs[:8])
                text = f"📑 *Invoices ({len(invs)})*\n{lines}"
    return text, buttons


_HELP = (
    "*Buchuchet bot* — operational assistant.\n\n"
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
