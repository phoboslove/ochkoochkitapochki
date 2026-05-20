"""Twilio WhatsApp adapter (skeleton)."""
from __future__ import annotations

from typing import Any

import httpx

from app.services.integrations.whatsapp.base import WhatsAppMessage, WhatsAppProvider


class TwilioWhatsApp(WhatsAppProvider):
    name = "twilio"

    def __init__(self, *, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number  # e.g. "whatsapp:+14155238886"

    async def send(self, msg: WhatsAppMessage) -> dict[str, Any]:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        data = {"From": self.from_number, "To": f"whatsapp:{msg.to}"}
        if msg.document_url:
            data["MediaUrl"] = msg.document_url
            data["Body"] = msg.text or msg.document_filename or ""
        else:
            data["Body"] = msg.text or ""
        async with httpx.AsyncClient(timeout=15, auth=(self.account_sid, self.auth_token)) as c:
            r = await c.post(url, data=data)
            r.raise_for_status()
            return r.json()

    async def parse_inbound(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        # Twilio posts urlencoded form fields; the caller normalizes to dict.
        return [{
            "from": (payload.get("From") or "").removeprefix("whatsapp:"),
            "text": payload.get("Body"),
            "type": "text",
            "raw": payload,
        }]

    async def verify_webhook(self, params: dict[str, Any]) -> str | None:
        return None  # Twilio uses signature header verification, not a challenge.
