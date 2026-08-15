"""Document service — upload, OCR pipeline, status tracking."""
from __future__ import annotations

import uuid

from fastapi import UploadFile
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document
from app.services.audit.logger import AuditLogger
from app.services.documents.ocr import get_ocr_provider
from app.services.documents.parser import parse
from app.services.storage import get_storage
from app.services.storage.base import Storage


_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.ms-excel",
    "image/png", "image/jpeg", "image/webp", "image/tiff",
    "text/plain",
}
_MAX_SIZE = 25 * 1024 * 1024  # 25 MB


def _kind_for(mime: str) -> str:
    if mime == "application/pdf":             return "PDF"
    if "wordprocessingml" in mime:            return "DOCX"
    if "spreadsheetml" in mime:               return "XLSX"
    if mime.startswith("image/"):             return "IMAGE"
    return "OTHER"


class DocumentService:
    def __init__(self) -> None:
        self.storage = get_storage()
        self.audit = AuditLogger()

    async def list(
        self, session: AsyncSession, company_id: str, *,
        limit: int | None = None, offset: int = 0,
    ) -> list[Document]:
        q = select(Document).where(Document.company_id == company_id).order_by(desc(Document.created_at))
        if limit is not None:
            q = q.limit(limit).offset(offset)
        rows = await session.scalars(q)
        return list(rows)

    async def get(self, session: AsyncSession, company_id: str, doc_id: str) -> Document | None:
        doc = await session.get(Document, doc_id)
        if not doc or doc.company_id != company_id:
            return None
        return doc

    async def upload(
        self, session: AsyncSession, *, company_id: str, actor_id: str,
        file: UploadFile, doc_type: str = "OTHER",
    ) -> Document:
        from app.services.limits.usage import assert_can_upload_document
        await assert_can_upload_document(session, company_id)
        content = await file.read()
        if len(content) > _MAX_SIZE:
            raise ValueError("file too large")
        mime = file.content_type or "application/octet-stream"
        if mime not in _ALLOWED_MIME:
            raise ValueError(f"unsupported mime: {mime}")

        doc_id = f"doc_{uuid.uuid4().hex[:10]}"
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
        key = f"{company_id}/documents/{doc_id}/{file.filename or 'upload'}.{ext}"
        self.storage.put(key, content, content_type=mime)

        doc = Document(
            id=doc_id, company_id=company_id,
            type=doc_type if doc_type != "OTHER" else _kind_for(mime),
            title=file.filename or "Untitled",
            storage_key=key, mime=mime, size=len(content),
            checksum=Storage.checksum(content), status="OCR_PENDING",
            created_by=actor_id, meta={"original_name": file.filename},
        )
        session.add(doc)
        await self.audit.record(
            session, company_id=company_id, actor_type="user", actor_id=actor_id,
            action="document.upload", resource=doc.id,
            meta={"size": len(content), "mime": mime},
        )
        await session.flush()

        # Inline OCR for the MVP. Production: enqueue + worker.
        await self._run_ocr(session, doc, content, mime)
        return doc

    async def retry(self, session: AsyncSession, doc: Document) -> Document:
        """Re-run OCR + parse on a previously failed/incomplete document."""
        try:
            content = self.storage.get(doc.storage_key)
        except Exception as exc:  # noqa: BLE001
            doc.status = "FAILED"
            doc.meta = {**(doc.meta or {}), "error": f"storage: {exc}"}
            return doc
        doc.status = "OCR_PENDING"
        await self._run_ocr(session, doc, content, doc.mime)
        return doc

    async def _run_ocr(self, session: AsyncSession, doc: Document, content: bytes, mime: str) -> None:
        from app.services.documents.ocr import LOW_CONFIDENCE_THRESHOLD
        try:
            ocr = await get_ocr_provider().extract(content=content, mime=mime)
            doc.ocr_text = ocr.get("text")
            confidence = float(ocr.get("confidence", 1.0))
            warnings = list(ocr.get("warnings", []))
            doc.status = "OCR_DONE"
            doc.parsed = parse(doc.type.lower(), doc.ocr_text or "")
            doc.meta = {
                **(doc.meta or {}),
                "ocr_confidence": confidence,
                "ocr_warnings": warnings,
                "rotation": ocr.get("rotation", 0),
                "needs_review": confidence < LOW_CONFIDENCE_THRESHOLD or bool(warnings),
            }
            doc.status = "PARSED"
            await self.audit.record(
                session, company_id=doc.company_id, actor_type="system",
                action="document.parsed", resource=doc.id,
                meta={"confidence": confidence, "warnings": warnings},
            )
        except Exception as exc:  # noqa: BLE001
            doc.status = "FAILED"
            doc.meta = {**(doc.meta or {}), "error": str(exc)}
            await self.audit.record(
                session, company_id=doc.company_id, actor_type="system",
                action="document.failed", resource=doc.id, meta={"error": str(exc)},
            )
            from app.core.monitoring import capture_workflow_failure
            capture_workflow_failure(run_id=doc.id, step="document.ocr", error=str(exc),
                                     extra={"mime": doc.mime, "size": doc.size})
