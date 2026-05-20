"""Provider-agnostic Telegram interface.

Mirrors `WhatsAppProvider` so the rest of the app stays channel-uniform.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InlineButton:
    text: str
    callback_data: str | None = None
    url: str | None = None


@dataclass
class TelegramMessage:
    chat_id: str
    text: str
    parse_mode: str = "Markdown"
    buttons: list[list[InlineButton]] = field(default_factory=list)


class TelegramProvider(ABC):
    name: str

    @abstractmethod
    async def send(self, msg: TelegramMessage) -> dict[str, Any]: ...

    @abstractmethod
    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> dict[str, Any]: ...

    @abstractmethod
    async def parse_inbound(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize Telegram update to ``[{kind, from_user, chat_id, text, callback_data, ...}]``."""

    def verify_secret(self, header_token: str | None) -> bool:
        """Webhook secret check (X-Telegram-Bot-Api-Secret-Token)."""
        return True
