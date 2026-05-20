from typing import Any
from app.services.integrations.base import IntegrationAdapter


class BitrixAdapter(IntegrationAdapter):
    provider = "bitrix"

    async def connect(self, config): return {"provider": self.provider, "status": "connected"}
    async def test(self): return {"provider": self.provider, "ok": True}
