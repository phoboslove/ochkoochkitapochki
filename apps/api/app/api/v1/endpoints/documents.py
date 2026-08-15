from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.core.ratelimit import rate_limit

# Document generation hits LibreOffice + writes to storage — 30/min/IP is
# more than any operator will ever need and still cheap to absorb.
_generate_limit = rate_limit("documents.generate", limit=30, window_s=60)
_upload_limit   = rate_limit("documents.upload",   limit=30, window_s=60)
from app.db.models import Document
from app.services.audit.logger import AuditLogger
from app.services.documents.service import DocumentService
from app.services.storage import get_storage

router = APIRouter()
service = DocumentService()
audit = AuditLogger()


def _serialize(d: Document) -> dict:
    return {
        "id": d.id, "title": d.title, "type": d.type, "mime": d.mime, "size": d.size,
        "status": d.status, "created_at": d.created_at.isoformat(),
        "checksum": d.checksum, "parsed": d.parsed,
        "preview_url": get_storage().presign_get(d.storage_key, expires_in=3600) if d.storage_key else None,
    }


class PatchFieldsIn(BaseModel):
    parsed: dict


@router.get("")
async def list_documents(
    limit: int | None = None,
    offset: int = 0,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await service.list(session, user.company_id, limit=limit, offset=offset)
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


class GenerateIn(BaseModel):
    kind: str
    prompt: str | None = None
    client_name: str | None = None
    total: float | None = None
    currency: str = "KZT"
    item_description: str | None = None
    qty: float = 1
    vat_percent: float | None = None
    notes: str | None = None


@router.post("/generate", dependencies=[Depends(_generate_limit)])
async def generate_document(
    body: GenerateIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Direct (non-AI) entrypoint to the generation pipeline.

    Used by the templates UI 'Generate' button and integration tests; the AI
    assistant reaches the same code via the `generate_document` tool.
    """
    from app.services.documents.generation import GenerationPipeline, SUPPORTED_KINDS
    kind = (body.kind or "").strip().lower()
    if kind not in SUPPORTED_KINDS:
        raise HTTPException(400, f"unsupported kind: {body.kind!r}; pick one of {sorted(SUPPORTED_KINDS)}")
    overrides = {
        "client_name": body.client_name, "total": body.total, "currency": body.currency,
        "item_description": body.item_description, "qty": body.qty,
        "vat_percent": body.vat_percent, "notes": body.notes,
    }
    overrides = {k: v for k, v in overrides.items() if v not in (None, "")}
    try:
        result = await GenerationPipeline().generate(
            session, company_id=user.company_id, actor_id=user.id,
            actor_type="user", kind=kind, prompt=body.prompt, overrides=overrides,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await session.commit()
    return {
        "document_id":   result.document_id,
        "kind":          result.kind,
        "number":        result.document_number,
        "template_id":      result.template_id,
        "template_name":    result.template_name,
        "template_verified": result.template_verified,
        "template_operational_score": result.template_operational_score,
        "match_reason":  result.match_reason,
        "match_score":   result.match_score,
        "pdf_url":       result.pdf_url,
        "docx_url":      result.docx_url,
        "primary_url":   result.primary_url,
        "approval_id":     result.approval_id,
        "approval_status": result.approval_status,
        "render_ms":       result.render_duration_ms,
        "quality":         result.quality,
        "quality_status":  (result.quality or {}).get("status"),
        "quality_score":   (result.quality or {}).get("score"),
        "fallback_used":   result.fallback_used,
        "fallback_reason": result.fallback_reason,
        "fallback_engine": result.fallback_engine,
        "adaptation_applied": result.adaptation_applied,
        "adaptation_anchors_injected": result.adaptation_anchors_injected,
        "diagnostics":     result.diagnostics,
        "warnings":        result.warnings,
    }


@router.post("/upload", dependencies=[Depends(_upload_limit)])
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
