"""Meta WhatsApp Cloud API adapter (skeleton)."""
from __future__ import annotations

from typing import Any

import httpx

from app.services.integrations.whatsapp.base import WhatsAppMessage, WhatsAppProvider


class MetaCloudWhatsApp(WhatsAppProvider):
    name = "meta_cloud"

    def __init__(
        self, *, phone_number_id: str, access_token: str,
        verify_token: str | None = None, app_secret: str | None = None,
    ):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.verify_token = verify_token
        self.app_secret = app_secret

    def verify_signature(self, raw_body: bytes, header_sig: str | None) -> bool:
        """Validate ``X-Hub-Signature-256: sha256=<hex>``. Returns True if no
        ``app_secret`` is configured (dev) — wire one in production."""
        if not self.app_secret:
            return True
        if not header_sig or not header_sig.startswith("sha256="):
            return False
        import hashlib, hmac
        expected = hmac.new(self.app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, header_sig.removeprefix("sha256="))

    @property
    def _base(self) -> str:
        return f"https://graph.facebook.com/v20.0/{self.phone_number_id}"

    async def send(self, msg: WhatsAppMessage) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if msg.document_url:
            body = {"messaging_product": "whatsapp", "to": msg.to, "type": "document",
                    "document": {"link": msg.document_url, "filename": msg.document_filename or "document"}}
        else:
            body = {"messaging_product": "whatsapp", "to": msg.to, "type": "text",
                    "text": {"body": msg.text or ""}}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{self._base}/messages", json=body, headers=headers)
            r.raise_for_status()
            return r.json()

    async def parse_inbound(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for m in value.get("messages", []):
                    out.append({
                        "from": m.get("from"),
                        "text": (m.get("text") or {}).get("body"),
                        "type": m.get("type"),
                        "raw": m,
                    })
        return out

    async def verify_webhook(self, params: dict[str, Any]) -> str | None:
        # Meta GET verification: hub.mode=subscribe + hub.verify_token + hub.challenge
        if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == self.verify_token:
            return params.get("hub.challenge")
        return None
