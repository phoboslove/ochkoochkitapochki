"""Cloudflare Turnstile verification — bot protection on register/login.

No-op (always passes) when TURNSTILE_SECRET_KEY isn't set, matching the
same "optional external integration, graceful local fallback" pattern
already used for S3's public endpoint and the email providers. Local dev
never needs a Cloudflare account to run the app."""
from __future__ import annotations

import os

import httpx

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    secret = os.environ.get("TURNSTILE_SECRET_KEY")
    if not secret:
        return True
    if not token:
        return False
    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(_VERIFY_URL, data=data)
            r.raise_for_status()
            return bool(r.json().get("success"))
    except httpx.HTTPError:
        # Cloudflare hiccup shouldn't lock everyone out of registering/logging in.
        from app.core.logging import log
        log.exception("turnstile_verify_failed")
        return True
