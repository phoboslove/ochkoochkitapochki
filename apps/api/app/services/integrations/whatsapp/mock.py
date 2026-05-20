"""Mock provider for dev/tests."""
from __future__ import annotations

from typing import Any

from app.services.integrations.whatsapp.base import WhatsAppMessage, WhatsAppProvider


class MockWhatsApp(WhatsAppProvider):
    name = "mock"

    async def send(self, msg: WhatsAppMessage) -> dict[str, Any]:
        return {"queued": True, "to": msg.to, "preview": (msg.text or "")[:80]}

    async def parse_inbound(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"from": payload.get("from_phone", "+0"), "text": payload.get("text", ""), "type": "text"}]

    async def verify_webhook(self, params: dict[str, Any]) -> str | None:
        return None
