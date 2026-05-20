"""Mock provider for dev/tests."""
from __future__ import annotations

from typing import Any

from app.core.logging import log
from app.services.integrations.telegram.base import TelegramMessage, TelegramProvider


class MockTelegram(TelegramProvider):
    name = "mock"

    async def send(self, msg: TelegramMessage) -> dict[str, Any]:
        log.info("telegram.mock.send", chat_id=msg.chat_id, text=msg.text[:120],
                 buttons=[[b.text for b in row] for row in msg.buttons])
        return {"ok": True, "result": {"message_id": 0}}

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> dict[str, Any]:
        return {"ok": True}

    async def parse_inbound(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"kind": "message", "from_user": "0", "chat_id": "0",
                 "text": payload.get("text", "")}]
