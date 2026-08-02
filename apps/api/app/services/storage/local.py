"""Local-filesystem storage adapter."""
from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.services.storage.base import Storage, sign_local_url


class LocalStorage(Storage):
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root)):
            raise ValueError("path traversal blocked")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put(self, key: str, body: bytes, *, content_type: str) -> str:
        self._path(key).write_bytes(body)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def presign_get(self, key: str, *, expires_in: int = 600) -> str:
        return sign_local_url(key, expires_in=expires_in)
