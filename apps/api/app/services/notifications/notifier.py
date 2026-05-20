"""Notification dispatcher — multi-channel (email, in-app, WhatsApp)."""
from __future__ import annotations

from typing import Any


class Notifier:
    async def notify(self, *, channel: str, to: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Scaffold: route to integration manager when channel == "whatsapp" etc.
        return {"channel": channel, "to": to, "delivered": True}
