"""Resolve a provider for a company from its Integration config."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Integration
from app.services.integrations.whatsapp.base import WhatsAppProvider
from app.services.integrations.whatsapp.meta import MetaCloudWhatsApp
from app.services.integrations.whatsapp.mock import MockWhatsApp
from app.services.integrations.whatsapp.twilio import TwilioWhatsApp


async def build_whatsapp_provider(session: AsyncSession, company_id: str) -> WhatsAppProvider:
    integration = await session.scalar(
        select(Integration).where(Integration.company_id == company_id, Integration.provider == "whatsapp"),
    )
    if not integration or integration.status != "connected":
        return MockWhatsApp()

    cfg = integration.config or {}
    sec = integration.secrets or {}
    sub = cfg.get("provider", "mock")

    if sub == "meta_cloud":
        return MetaCloudWhatsApp(
            phone_number_id=cfg["phone_number_id"],
            access_token=sec["access_token"],
            verify_token=sec.get("verify_token"),
            app_secret=sec.get("app_secret"),
        )
    if sub == "twilio":
        return TwilioWhatsApp(
            account_sid=cfg["account_sid"],
            auth_token=sec["auth_token"],
            from_number=cfg["from_number"],
        )
    return MockWhatsApp()
