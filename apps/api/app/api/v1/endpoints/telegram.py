"""Telegram-specific endpoints — webhook, linking, status, prefs.

The general-purpose Integration connect/disconnect lives in
`endpoints/integrations.py`; this router is for Telegram-only flows.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.db.models import Integration, User
from app.services.integrations.telegram import build_telegram_provider
from app.services.integrations.telegram.service import create_link_token, handle_update

router = APIRouter()


# ── Webhook ────────────────────────────────────────────────────────────────

@router.post("/{company_id}")
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
    return {
        "linked": bool(target and target.telegram_user_id),
        "telegram_username": target.telegram_username if target else None,
        "notify_telegram": target.notify_telegram if target else False,
        "notify_email":    target.notify_email if target else True,
        "bot_connected":   bool(integration and integration.status == "connected"),
        "bot_username":    (integration.config or {}).get("bot_username") if integration else None,
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
