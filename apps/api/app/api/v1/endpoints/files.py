"""Serve stored files with signed-URL or bearer+ACL access (local backend)."""
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response

from app.core.security import decode_token
from app.services.storage import get_storage
from app.services.storage.base import Storage, verify_local_url
from app.services.storage.local import LocalStorage

router = APIRouter()

_MIME = {
    "html": "text/html", "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "txt": "text/plain",
}


def _mime_for(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return _MIME.get(ext, "application/octet-stream")


@router.get("/{path:path}")
async def get_file(
    path: str,
    sig: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
):
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(400, "non-local storage uses provider presigned URLs")

    # Path 1 — signed URL (no Authorization header needed; safe to embed).
    if sig and verify_local_url(path, sig):
        try:
            body = storage.get(path)
        except FileNotFoundError:
            raise HTTPException(404, "not found")
        return Response(body, media_type=_mime_for(path))

    # Path 2 — bearer auth + tenant ACL.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token or signature")
    try:
        payload = decode_token(authorization.removeprefix("Bearer "))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(401, "invalid token") from exc
    if Storage.company_of(path) != payload.get("company_id"):
        raise HTTPException(403, "forbidden")
    try:
        body = storage.get(path)
    except FileNotFoundError:
        raise HTTPException(404, "not found")
    return Response(body, media_type=_mime_for(path))
