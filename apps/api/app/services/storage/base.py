"""Storage interface — local + S3 share the same surface.

Keys are namespaced ``{company_id}/{kind}/{id}/{filename}`` so an ACL check
can be done by inspecting the prefix.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import settings


class Storage(ABC):
    @abstractmethod
    def put(self, key: str, body: bytes, *, content_type: str) -> str: ...
    @abstractmethod
    def get(self, key: str) -> bytes: ...
    @abstractmethod
    def presign_get(self, key: str, *, expires_in: int = 600) -> str: ...

    # Convenience: extract the company prefix from a key for ACL checks.
    @staticmethod
    def company_of(key: str) -> str | None:
        head, _, _ = key.partition("/")
        return head or None

    @staticmethod
    def checksum(body: bytes) -> str:
        return hashlib.sha256(body).hexdigest()


# ── Lightweight signed-URL token used by LocalStorage ──────────────────────

def sign_local_url(key: str, *, expires_in: int = 600) -> str:
    exp = int((datetime.now(timezone.utc) + timedelta(seconds=expires_in)).timestamp())
    token = jwt.encode({"k": key, "exp": exp}, settings.jwt_secret, algorithm=settings.jwt_alg)
    return f"/api/v1/files/{key}?sig={token}"


def verify_local_url(key: str, sig: str) -> bool:
    try:
        payload = jwt.decode(sig, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except Exception:  # noqa: BLE001
        return False
    return payload.get("k") == key
