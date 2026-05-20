from typing import Any
from app.services.integrations.base import IntegrationAdapter


class TelegramAdapter(IntegrationAdapter):
    provider = "telegram"

    async def connect(self, config): return {"provider": self.provider, "status": "connected"}
    async def test(self): return {"provider": self.provider, "ok": True}
    async def send(self, payload): return {"provider": self.provider, "queued": True}
