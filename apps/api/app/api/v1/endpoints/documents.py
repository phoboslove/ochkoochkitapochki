from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.db.models import Document
from app.services.audit.logger import AuditLogger
from app.services.documents.service import DocumentService
from app.services.storage.base import sign_local_url

router = APIRouter()
service = DocumentService()
audit = AuditLogger()


def _serialize(d: Document) -> dict:
    return {
        "id": d.id, "title": d.title, "type": d.type, "mime": d.mime, "size": d.size,
        "status": d.status, "created_at": d.created_at.isoformat(),
        "checksum": d.checksum, "parsed": d.parsed,
        "preview_url": sign_local_url(d.storage_key, expires_in=3600) if d.storage_key else None,
    }


class PatchFieldsIn(BaseModel):
    parsed: dict


@router.get("")
async def list_documents(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await service.list(session, user.company_id)
    return [_serialize(r) for r in rows]


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    d = await service.get(session, user.company_id, doc_id)
    if not d:
        raise HTTPException(404, "not found")
    return {**_serialize(d), "ocr_text": d.ocr_text}


@router.patch("/{doc_id}/fields")
async def update_fields(
    doc_id: str, body: PatchFieldsIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    d = await service.get(session, user.company_id, doc_id)
    if not d:
        raise HTTPException(404, "not found")
    d.parsed = {**(d.parsed or {}), **body.parsed}
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="document.fields_updated", resource=d.id, meta={"keys": list(body.parsed.keys())},
    )
    await session.commit()
    return _serialize(d)


@router.post("/{doc_id}/retry")
async def retry_doc(
    doc_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    d = await service.get(session, user.company_id, doc_id)
    if not d:
        raise HTTPException(404, "not found")
    await service.retry(session, d)
    await session.commit()
    return _serialize(d)


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    doc_type: str = Form(default="OTHER"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        doc = await service.upload(session, company_id=user.company_id, actor_id=user.id, file=file, doc_type=doc_type)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await session.commit()
    return _serialize(doc)
