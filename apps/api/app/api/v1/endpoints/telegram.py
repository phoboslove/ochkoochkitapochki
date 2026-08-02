"""Telegram-specific endpoints — webhook, linking, status, prefs, bot connect.

The general-purpose Integration connect/disconnect lives in
`endpoints/integrations.py`; this router is for Telegram-only flows including
per-workspace bot connection (token verify + auto-webhook registration).
"""
from __future__ import annotations

import secrets as _secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.core.logging import log
from app.core.ratelimit import rate_limit
from app.db.models import AuditLog, Integration, User

# Webhook gets hit by Telegram up to a few per second per chat — a generous
# 120/min/IP is loose enough for real traffic but stops floods that would
# drain OpenAI credits.
_webhook_limit = rate_limit("telegram.webhook", limit=120, window_s=60)
_connect_limit = rate_limit("telegram.connect", limit=10,  window_s=60)
from app.services.audit.logger import AuditLogger
from app.services.integrations.telegram import build_telegram_provider
from app.services.integrations.telegram.bot import BotApiTelegram
from app.services.integrations.telegram.service import create_link_token, handle_update

router = APIRouter()
_audit = AuditLogger()


# ── Bot connect / disconnect (per-workspace) ──────────────────────────────


class BotConnectIn(BaseModel):
    bot_token: str = Field(..., min_length=20, description="Token from @BotFather.")
    public_webhook_base: str | None = Field(
        None,
        description=(
            "HTTPS base URL the public internet uses to reach this API "
            "(e.g. https://ops.example.com). If absent, the webhook is "
            "registered against the request's own Origin/Host — which only "
            "works when the API itself is publicly reachable over HTTPS."
        ),
    )


def _derive_webhook_base(req: Request, override: str | None) -> str | None:
    """Best-effort public base URL. Telegram requires HTTPS — http URLs from
    local dev are returned but flagged as 'will fail to register'."""
    if override:
        return override.rstrip("/")
    # Honour any reverse-proxy headers in case the API is behind nginx.
    proto = req.headers.get("x-forwarded-proto") or req.url.scheme
    host = req.headers.get("x-forwarded-host") or req.headers.get("host")
    if not host:
        return None
    return f"{proto}://{host}"


@router.post("/bot/connect", dependencies=[Depends(_connect_limit)])
async def connect_bot(
    body: BotConnectIn,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Connect a per-workspace Telegram bot:
      1) Validate the token with Telegram's `getMe`.
      2) Generate a webhook secret.
      3) If a public HTTPS base URL is available, call `setWebhook`.
      4) Persist token + secret + bot username in the Integration row.

    Tokens are stored in `Integration.secrets` (JSON column). They are NEVER
    returned in responses or written to audit logs — only the bot username
    and webhook status are exposed.
    """
    if user.role not in ("OWNER", "ADMIN"):
        raise HTTPException(403, "admin only")

    # 1) Verify token with Telegram before we save anything.
    provider = BotApiTelegram(bot_token=body.bot_token)
    try:
        me = await provider.get_me()
    except Exception as exc:  # noqa: BLE001
        # Don't log the token or the raw response — only a redacted error class.
        log.warning("telegram.connect.getme_failed",
                     company_id=user.company_id, err_type=type(exc).__name__)
        raise HTTPException(400, "Telegram rejected the token (getMe failed). "
                                  "Check that the token was copied from @BotFather correctly.")
    if not me.get("ok"):
        raise HTTPException(400, "Telegram returned ok=false for getMe.")
    bot = me.get("result") or {}
    bot_username = bot.get("username")
    bot_id = bot.get("id")
    if not bot_username:
        raise HTTPException(400, "Bot reported no username — connect a regular bot (not a userbot).")

    # 2) Generate a webhook secret (Telegram limits to alphanumerics + few symbols, max 256).
    webhook_secret = _secrets.token_urlsafe(32).replace("-", "x").replace("_", "y")[:64]

    # 3) Register webhook if we can derive a public URL.
    webhook_url: str | None = None
    webhook_registered = False
    webhook_error: str | None = None
    base = _derive_webhook_base(request, body.public_webhook_base)
    if base:
        webhook_url = f"{base}/api/v1/telegram/{user.company_id}"
        if webhook_url.startswith("https://"):
            try:
                result = await provider.set_webhook(webhook_url, webhook_secret)
                if result.get("ok"):
                    webhook_registered = True
                else:
                    webhook_error = (result.get("description") or "telegram returned ok=false")
            except Exception as exc:  # noqa: BLE001
                webhook_error = f"setWebhook raised: {type(exc).__name__}"
        else:
            webhook_error = (
                f"Webhook URL is not HTTPS ({webhook_url}). Telegram requires HTTPS. "
                "Deploy behind a public TLS endpoint or pass `public_webhook_base` "
                "with your https origin."
            )
    else:
        webhook_error = "Could not derive a public base URL from request headers."

    # 4) Upsert Integration row.
    integration = await session.scalar(
        select(Integration).where(
            Integration.company_id == user.company_id, Integration.provider == "telegram",
        ),
    )
    if not integration:
        integration = Integration(
            id=f"int_{uuid.uuid4().hex[:10]}",
            company_id=user.company_id, provider="telegram",
            status="connected", config={}, secrets={},
        )
        session.add(integration)
    integration.status = "connected"
    integration.secrets = {
        **(integration.secrets or {}),
        "bot_token": body.bot_token,
        "webhook_secret": webhook_secret,
    }
    integration.config = {
        **(integration.config or {}),
        "bot_username": bot_username,
        "bot_id": bot_id,
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "webhook_url": webhook_url,
        "webhook_registered": webhook_registered,
        "webhook_error": webhook_error,
    }

    await _audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="telegram.bot_connected", resource=integration.id,
        meta={"bot_username": bot_username, "webhook_registered": webhook_registered,
              "webhook_error": webhook_error[:120] if webhook_error else None},
    )
    await session.commit()

    return {
        "ok": True,
        "bot_username": bot_username,
        "bot_id": bot_id,
        "webhook_url": webhook_url,
        "webhook_registered": webhook_registered,
        "webhook_error": webhook_error,
    }


@router.post("/bot/disconnect")
async def disconnect_bot(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if user.role not in ("OWNER", "ADMIN"):
        raise HTTPException(403, "admin only")
    integration = await session.scalar(
        select(Integration).where(
            Integration.company_id == user.company_id, Integration.provider == "telegram",
        ),
    )
    if not integration:
        return {"ok": True, "note": "telegram was not connected"}

    # Best-effort: tell Telegram to forget our webhook before we drop the token.
    deleted = False
    token = (integration.secrets or {}).get("bot_token")
    if token:
        try:
            provider = BotApiTelegram(bot_token=token)
            res = await provider.delete_webhook()
            deleted = bool(res.get("ok"))
        except Exception as exc:  # noqa: BLE001
            log.warning("telegram.disconnect.delete_webhook_failed",
                         company_id=user.company_id, err_type=type(exc).__name__)

    integration.status = "disconnected"
    # Wipe sensitive bits but keep history of the bot username for audit clarity.
    integration.secrets = {}
    integration.config = {
        **(integration.config or {}),
        "webhook_registered": False, "webhook_url": None,
        "disconnected_at": datetime.now(timezone.utc).isoformat(),
    }
    await _audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="telegram.bot_disconnected", resource=integration.id,
        meta={"webhook_deleted": deleted},
    )
    await session.commit()
    return {"ok": True, "webhook_deleted": deleted}


# ── Webhook ────────────────────────────────────────────────────────────────

@router.post("/{company_id}", dependencies=[Depends(_webhook_limit)])
async def webhook(company_id: str, request: Request,
                  session: AsyncSession = Depends(get_session)) -> dict:
    provider = await build_telegram_provider(session, company_id)
    secret_header = request.headers.get("x-telegram-bot-api-secret-token")
    if not provider.verify_secret(secret_header):
        raise HTTPException(401, "invalid telegram webhook secret")
    payload = await request.json()
    updates = await provider.parse_inbound(payload)
    for u in updates:
        await handle_update(session, company_id=company_id, update=u)
    await session.commit()
    return {"ok": True, "processed": len(updates)}


# ── Identity linking ───────────────────────────────────────────────────────

@router.post("/link/start")
async def link_start(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Issue a one-shot token. Returns a deep link the user opens in Telegram."""
    integration = await session.scalar(
        select(Integration).where(
            Integration.company_id == user.company_id, Integration.provider == "telegram",
        ),
    )
    if not integration or integration.status != "connected":
        raise HTTPException(400, "Telegram is not connected for this organization")
    bot_username = (integration.config or {}).get("bot_username")
    if not bot_username:
        raise HTTPException(400, "Telegram bot_username is not configured")

    link = await create_link_token(session, user_id=user.id, company_id=user.company_id)
    await session.commit()
    return {
        "token": link.token,
        "deep_link": f"https://t.me/{bot_username}?start={link.token}",
        "expires_at": link.expires_at.isoformat(),
    }


@router.post("/link/disconnect")
async def link_disconnect(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    target = await session.get(User, user.id)
    if target:
        target.telegram_user_id = None
        target.telegram_username = None
        await session.commit()
    return {"ok": True}


@router.get("/me")
async def me_status(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    target = await session.get(User, user.id)
    integration = await session.scalar(
        select(Integration).where(
            Integration.company_id == user.company_id, Integration.provider == "telegram",
        ),
    )

    # Surface the most recent inbound update for the operator's status panel.
    # The webhook handler records `telegram.message_received` for every
    # incoming update, so this is the cheapest "is the bot actually live?"
    # signal we have.
    last_event_at: str | None = None
    last_event = await session.scalar(
        select(AuditLog).where(
            AuditLog.company_id == user.company_id,
            AuditLog.action == "telegram.message_received",
        ).order_by(desc(AuditLog.at)).limit(1),
    )
    if last_event:
        last_event_at = last_event.at.isoformat()

    cfg = (integration.config or {}) if integration else {}
    return {
        "linked": bool(target and target.telegram_user_id),
        "telegram_username": target.telegram_username if target else None,
        "notify_telegram": target.notify_telegram if target else False,
        "notify_email":    target.notify_email if target else True,
        "bot_connected":   bool(integration and integration.status == "connected"),
        "bot_username":    cfg.get("bot_username"),
        "bot_id":          cfg.get("bot_id"),
        "webhook_url":     cfg.get("webhook_url"),
        "webhook_registered": bool(cfg.get("webhook_registered")),
        "webhook_error":   cfg.get("webhook_error"),
        "connected_at":    cfg.get("connected_at"),
        "last_event_at":   last_event_at,
    }


class PrefsIn(BaseModel):
    notify_telegram: bool | None = None
    notify_email: bool | None = None


@router.patch("/preferences")
async def update_prefs(
    body: PrefsIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    target = await session.get(User, user.id)
    if not target:
        raise HTTPException(404, "user not found")
    if body.notify_telegram is not None: target.notify_telegram = body.notify_telegram
    if body.notify_email is not None:    target.notify_email = body.notify_email
    await session.commit()
    return {"notify_telegram": target.notify_telegram, "notify_email": target.notify_email}


# ── Bot administration (set/clear webhook) ─────────────────────────────────

class WebhookIn(BaseModel):
    url: str
    secret_token: str | None = None


@router.post("/webhook/set")
async def set_webhook(
    body: WebhookIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if user.role not in ("OWNER", "ADMIN"):
        raise HTTPException(403, "admin only")
    provider = await build_telegram_provider(session, user.company_id)
    if hasattr(provider, "set_webhook"):
        result = await provider.set_webhook(body.url, body.secret_token)  # type: ignore[attr-defined]
        # Persist secret on integration so verify_secret can compare.
        if body.secret_token:
            integration = await session.scalar(
                select(Integration).where(
                    Integration.company_id == user.company_id, Integration.provider == "telegram",
                ),
            )
            if integration:
                integration.secrets = {**(integration.secrets or {}), "webhook_secret": body.secret_token}
                await session.commit()
        return {"ok": True, "result": result}
    raise HTTPException(400, "Telegram provider does not support webhook management")
