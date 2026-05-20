"""Resolve a Telegram provider for a company from its Integration row."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Integration
from app.services.integrations.telegram.base import TelegramProvider
from app.services.integrations.telegram.bot import BotApiTelegram
from app.services.integrations.telegram.mock import MockTelegram


async def build_telegram_provider(session: AsyncSession, company_id: str) -> TelegramProvider:
    integration = await session.scalar(
        select(Integration).where(
            Integration.company_id == company_id, Integration.provider == "telegram",
        ),
    )
    if not integration or integration.status != "connected":
        return MockTelegram()
    cfg = integration.config or {}
    sec = integration.secrets or {}
    token = sec.get("bot_token")
    if not token:
        return MockTelegram()
    return BotApiTelegram(
        bot_token=token,
        webhook_secret=sec.get("webhook_secret"),
        bot_username=cfg.get("bot_username"),
    )
