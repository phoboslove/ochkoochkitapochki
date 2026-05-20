from typing import Any

from app.services.integrations.base import IntegrationAdapter


class WhatsAppAdapter(IntegrationAdapter):
    provider = "whatsapp"

    async def connect(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"provider": self.provider, "status": "connected"}

    async def test(self) -> dict[str, Any]:
        return {"provider": self.provider, "ok": True}

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        # TODO: call provider API (Meta Cloud, 360dialog, Wazzup24…)
        return {"provider": self.provider, "queued": True, "to": payload.get("to")}
