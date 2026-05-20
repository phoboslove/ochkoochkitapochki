"""Integration manager — uniform façade over all provider adapters."""
from __future__ import annotations

from typing import Any

from app.services.integrations.base import IntegrationAdapter
from app.services.integrations.bitrix import BitrixAdapter
from app.services.integrations.kaspi import KaspiAdapter
from app.services.integrations.telegram import TelegramAdapter
from app.services.integrations.whatsapp import WhatsAppAdapter


class IntegrationManager:
    def __init__(self) -> None:
        self._adapters: dict[str, IntegrationAdapter] = {
            a.provider: a
            for a in (WhatsAppAdapter(), TelegramAdapter(), BitrixAdapter(), KaspiAdapter())
        }

    def list_demo(self) -> list[dict[str, Any]]:
        return [
            {"provider": "whatsapp", "name": "WhatsApp Business", "status": "connected"},
            {"provider": "telegram", "name": "Telegram",         "status": "disconnected"},
            {"provider": "bitrix",   "name": "Bitrix24",         "status": "connected"},
            {"provider": "amocrm",   "name": "amoCRM",           "status": "disconnected"},
            {"provider": "kaspi",    "name": "Kaspi.kz",         "status": "disconnected"},
            {"provider": "ozon",     "name": "Ozon",             "status": "disconnected"},
            {"provider": "gsheets",  "name": "Google Sheets",    "status": "connected"},
            {"provider": "gmail",    "name": "Gmail",            "status": "disconnected"},
            {"provider": "gdrive",   "name": "Google Drive",     "status": "disconnected"},
            {"provider": "1c",       "name": "1C",               "status": "disconnected"},
        ]

    async def connect(self, provider: str, config: dict[str, Any]) -> dict[str, Any]:
        return await self._adapters[provider].connect(config)

    async def test(self, provider: str) -> dict[str, Any]:
        return await self._adapters[provider].test()

    async def send(self, provider: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._adapters[provider].send(payload)
