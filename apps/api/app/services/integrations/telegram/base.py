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


@dataclass
class TelegramDocument:
    """Outbound PDF/DOCX attachment.

    Exactly one of ``url`` (Telegram fetches the file itself) or ``content``
    (we upload raw bytes via multipart/form-data) must be set. ``url`` is
    preferred for storage-backed previews because it avoids re-uploading; bytes
    is the fallback for local-only files.
    """
    chat_id: str
    filename: str
    caption: str = ""
    parse_mode: str = "Markdown"
    url: str | None = None
    content: bytes | None = None
    buttons: list[list[InlineButton]] = field(default_factory=list)


class TelegramProvider(ABC):
    name: str

    @abstractmethod
    async def send(self, msg: TelegramMessage) -> dict[str, Any]: ...

    @abstractmethod
    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> dict[str, Any]: ...

    async def send_document(self, doc: TelegramDocument) -> dict[str, Any]:
        """Send a file as a Telegram document attachment. Concrete providers
        override; the mock falls through to a logged no-op."""
        raise NotImplementedError("provider does not support document attachments")

    @abstractmethod
    async def parse_inbound(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize Telegram update to ``[{kind, from_user, chat_id, text, callback_data, ...}]``."""

    def verify_secret(self, header_token: str | None) -> bool:
        """Webhook secret check (X-Telegram-Bot-Api-Secret-Token).

        Default: DENY. A provider that genuinely doesn't need a secret
        (the in-memory mock used in tests) MUST explicitly override this
        to ``return True``. Real providers must have a configured secret —
        empty/null means the integration is half-configured and we refuse
        traffic. (CRITICAL #3 of the beta audit.)
        """
        return False
