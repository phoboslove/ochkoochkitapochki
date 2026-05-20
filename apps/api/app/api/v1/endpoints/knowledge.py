from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user, require_admin
from app.services.audit.logger import AuditLogger
from app.services.knowledge.service import KnowledgeService
from app.services.storage import get_storage

router = APIRouter()
service = KnowledgeService()
audit = AuditLogger()


def _serialize(d) -> dict:
    return {"id": d.id, "title": d.title, "tags": d.tags, "mime": d.mime,
            "has_body": bool(d.body), "storage_key": d.storage_key,
            "created_at": d.created_at.isoformat()}


class UpsertIn(BaseModel):
    id: str | None = None
    title: str
    body: str = ""
    tags: list[str] = []


@router.get("")
async def list_docs(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await service.list(session, user.company_id)
    return [_serialize(r) for r in rows]


@router.get("/{doc_id}")
async def get_doc(doc_id: str,
                  user: CurrentUser = Depends(get_current_user),
                  session: AsyncSession = Depends(get_session)) -> dict:
    doc = await service.get(session, user.company_id, doc_id)
    if not doc: raise HTTPException(404, "not found")
    return {**_serialize(doc), "body": doc.body}


@router.put("")
async def upsert(body: UpsertIn,
                 user: CurrentUser = Depends(require_admin),
                 session: AsyncSession = Depends(get_session)) -> dict:
    doc = await service.upsert(
        session, company_id=user.company_id, actor_id=user.id,
        title=body.title, body=body.body, tags=body.tags, doc_id=body.id,
    )
    await audit.record(session, company_id=user.company_id, actor_type="user",
                       actor_id=user.id, action="knowledge.upsert", resource=doc.id,
                       meta={"title": doc.title})
    await session.commit()
    return _serialize(doc)


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    title: str = Form(...),
    tags: str = Form(""),
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "max 5 MB for knowledge files")
    key = f"{user.company_id}/knowledge/{file.filename}"
    get_storage().put(key, content, content_type=file.content_type or "application/octet-stream")
    # Best-effort text extraction for retrieval. Markdown/plain texts inline; rest stored only.
    text_body = ""
    if (file.content_type or "").startswith("text/") or (file.filename or "").lower().endswith((".md", ".txt")):
        text_body = content.decode("utf-8", errors="ignore")[:50_000]
    doc = await service.upsert(
        session, company_id=user.company_id, actor_id=user.id,
        title=title, body=text_body, tags=[t.strip() for t in tags.split(",") if t.strip()],
        storage_key=key, mime=file.content_type,
    )
    await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                       action="knowledge.upload", resource=doc.id,
                       meta={"title": title, "mime": file.content_type})
    await session.commit()
    return _serialize(doc)


@router.delete("/{doc_id}")
async def delete(doc_id: str,
                 user: CurrentUser = Depends(require_admin),
                 session: AsyncSession = Depends(get_session)) -> dict:
    ok = await service.delete(session, user.company_id, doc_id)
    if not ok: raise HTTPException(404, "not found")
    await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                       action="knowledge.delete", resource=doc_id)
    await session.commit()
    return {"deleted": True}
