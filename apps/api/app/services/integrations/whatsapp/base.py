"""Provider-agnostic interface and DTOs."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class WhatsAppMessage:
    to: str
    text: str | None = None
    document_url: str | None = None
    document_filename: str | None = None


class WhatsAppProvider(ABC):
    name: str

    @abstractmethod
    async def send(self, msg: WhatsAppMessage) -> dict[str, Any]: ...

    @abstractmethod
    async def parse_inbound(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalize provider-specific webhook payload to: ``[{from, text, ...}]``."""

    @abstractmethod
    async def verify_webhook(self, params: dict[str, Any]) -> str | None:
        """Return challenge string for verification handshakes; None otherwise."""
