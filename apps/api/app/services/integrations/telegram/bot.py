"""Telegram Bot adapter using the Bot API directly via httpx (no SDK dep).

Implements `send`, `answer_callback`, `parse_inbound`, and webhook secret
verification. Polling-mode helper provided for local development.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.services.integrations.telegram.base import (
    InlineButton, TelegramDocument, TelegramMessage, TelegramProvider,
)


class BotApiTelegram(TelegramProvider):
    name = "bot_api"

    def __init__(self, *, bot_token: str, webhook_secret: str | None = None,
                 bot_username: str | None = None) -> None:
        self.bot_token = bot_token
        self.webhook_secret = webhook_secret
        self.bot_username = bot_username

    @property
    def _base(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    # ── Outbound ───────────────────────────────────────────────────────────

    async def send(self, msg: TelegramMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": msg.chat_id, "text": msg.text,
                                   "parse_mode": msg.parse_mode,
                                   "disable_web_page_preview": True}
        if msg.buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [_btn_payload(b) for b in row] for row in msg.buttons
                ],
            }
        return await self._post("sendMessage", payload)

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> dict[str, Any]:
        return await self._post("answerCallbackQuery",
                                {"callback_query_id": callback_query_id, **({"text": text} if text else {})})

    async def send_document(self, doc: TelegramDocument) -> dict[str, Any]:
        """sendDocument — Telegram fetches by URL when possible, falls back
        to multipart upload when raw bytes were supplied."""
        if doc.url and not doc.content:
            payload: dict[str, Any] = {
                "chat_id": doc.chat_id, "document": doc.url,
                "caption": doc.caption, "parse_mode": doc.parse_mode,
            }
            if doc.buttons:
                payload["reply_markup"] = {"inline_keyboard": [
                    [_btn_payload(b) for b in row] for row in doc.buttons
                ]}
            return await self._post("sendDocument", payload)

        if not doc.content:
            raise ValueError("TelegramDocument requires url or content")

        # Multipart upload path — used when we have bytes locally and either
        # the storage backend isn't publicly reachable or we want to bypass
        # Telegram's URL-fetch (e.g. for local development).
        data: dict[str, Any] = {
            "chat_id": doc.chat_id, "caption": doc.caption, "parse_mode": doc.parse_mode,
        }
        if doc.buttons:
            data["reply_markup"] = json.dumps({"inline_keyboard": [
                [_btn_payload(b) for b in row] for row in doc.buttons
            ]})
        files = {"document": (doc.filename, doc.content, "application/octet-stream")}
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self._base}/sendDocument", data=data, files=files)
            r.raise_for_status()
            return r.json()

    async def edit_message_reply_markup(self, *, chat_id: str, message_id: int,
                                         buttons: list[list[InlineButton]] | None) -> dict[str, Any]:
        body: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}
        if buttons:
            body["reply_markup"] = {"inline_keyboard": [[_btn_payload(b) for b in row] for row in buttons]}
        return await self._post("editMessageReplyMarkup", body)

    async def set_webhook(self, url: str, secret_token: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"url": url, "allowed_updates": ["message", "callback_query"]}
        if secret_token: payload["secret_token"] = secret_token
        return await self._post("setWebhook", payload)

    async def delete_webhook(self) -> dict[str, Any]:
        return await self._post("deleteWebhook", {})

    async def get_me(self) -> dict[str, Any]:
        return await self._post("getMe", {})

    # ── Inbound ────────────────────────────────────────────────────────────

    async def parse_inbound(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        if msg := payload.get("message"):
            out.append({
                "kind": "message",
                "update_id": payload.get("update_id"),
                "from_user": str((msg.get("from") or {}).get("id") or ""),
                "username":  (msg.get("from") or {}).get("username"),
                "chat_id":   str((msg.get("chat") or {}).get("id") or ""),
                "text":      (msg.get("text") or "").strip(),
            })

        if cb := payload.get("callback_query"):
            out.append({
                "kind": "callback_query",
                "update_id":         payload.get("update_id"),
                "callback_query_id": cb.get("id"),
                "from_user":         str((cb.get("from") or {}).get("id") or ""),
                "username":          (cb.get("from") or {}).get("username"),
                "chat_id":           str(((cb.get("message") or {}).get("chat") or {}).get("id") or ""),
                "message_id":        (cb.get("message") or {}).get("message_id"),
                "data":              cb.get("data"),
            })
        return out

    def verify_secret(self, header_token: str | None) -> bool:
        # Deny-by-default: a real bot with no configured webhook secret
        # is a half-finished integration. Refusing webhook traffic is the
        # safe failure mode — the operator sees nothing arriving and
        # reconnects via the UI (which now always generates a secret).
        if not self.webhook_secret:
            return False
        if not header_token:
            return False
        return header_token == self.webhook_secret

    # ── HTTP plumbing with retries ─────────────────────────────────────────

    async def _post(self, method: str, payload: dict[str, Any], *, attempts: int = 3) -> dict[str, Any]:
        delay = 0.5
        last_err: Exception | None = None
        for _ in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    r = await c.post(f"{self._base}/{method}", json=payload)
                # 429 — Telegram rate limit; honor retry_after
                if r.status_code == 429:
                    body = _safe_json(r)
                    retry_after = float((body.get("parameters") or {}).get("retry_after", 1))
                    await asyncio.sleep(retry_after)
                    continue
                r.raise_for_status()
                return r.json()
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_err = exc
                await asyncio.sleep(delay)
                delay *= 2
        raise RuntimeError(f"telegram api failed for {method}: {last_err}")


def _btn_payload(b: InlineButton) -> dict[str, Any]:
    out: dict[str, Any] = {"text": b.text}
    if b.callback_data is not None: out["callback_data"] = b.callback_data
    if b.url is not None:           out["url"] = b.url
    return out


def _safe_json(r: httpx.Response) -> dict[str, Any]:
    try: return r.json()
    except Exception: return {}
