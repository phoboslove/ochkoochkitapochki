"""Platform admin — document quality recheck.

When the render-QA rules change (required_fields.py) — or a genuine bug in
generation gets fixed — a document that's stuck BLOCKED under the old rules
can be re-evaluated here instead of hand-editing the database. Every recheck
is audited with actor_type="platform_admin", same mechanism as the rest of
/admin.

Recheck only works for documents generated after canonical-context capture
was added (pipeline.py persists it into Document.parsed["canonical"]) —
older documents return 422 and are left alone; there's no reliable way to
reconstruct their original render context.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, require_platform_admin
from app.db.models import Approval, Document
from app.services.audit.logger import AuditLogger
from app.services.documents.generation.quality import (
    QualityIssue, check_required_fields, score_report,
)

router = APIRouter()
audit = AuditLogger()


async def _latest_approval(session: AsyncSession, document_id: str) -> Approval | None:
    return await session.scalar(
        select(Approval)
        .where(Approval.resource_type == "document", Approval.resource_id == document_id)
        .order_by(Approval.created_at.desc()),
    )


def _document_out(doc: Document, approval: Approval | None) -> dict:
    parsed = doc.parsed or {}
    return {
        "id": doc.id, "company_id": doc.company_id, "title": doc.title,
        "type": doc.type, "status": doc.status, "created_at": doc.created_at.isoformat(),
        "kind": parsed.get("kind"),
        "document_number": parsed.get("document_number"),
        "recheck_available": parsed.get("canonical") is not None,
        "quality": parsed.get("quality"),
        "approval": ({
            "id": approval.id, "status": approval.status, "summary": approval.summary,
        } if approval else None),
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    _admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    approval = await _latest_approval(session, document_id)
    return _document_out(doc, approval)


@router.post("/documents/{document_id}/recheck-quality")
async def recheck_quality(
    document_id: str,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")

    parsed = doc.parsed or {}
    canonical = parsed.get("canonical")
    kind = parsed.get("kind")
    if canonical is None or not kind:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "this document predates canonical-context capture — recheck isn't available for it",
        )

    approval = await _latest_approval(session, document_id)
    if not approval:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no approval found for this document")

    old_quality = parsed.get("quality") or {}
    old_approval_status = approval.status

    # Keep every previously-computed issue EXCEPT the field-presence ones —
    # those are exactly what required_fields.py rules can change over time.
    # Artifact-level issues (leftover placeholders, malformed PDF, empty
    # table rows, ...) didn't change since the file wasn't re-rendered, so
    # they carry over unmodified.
    kept_issues = [
        QualityIssue(code=i["code"], message=i["message"], severity=i["severity"],
                     weight=i["weight"], where=i.get("where"))
        for i in (old_quality.get("issues") or [])
        if not str(i.get("code", "")).startswith("missing_")
    ]
    fresh_field_issues = check_required_fields(kind, canonical)
    report = score_report(kept_issues + fresh_field_issues, old_quality.get("stats") or {})

    still_blocked = report.status == "blocked" or any(i.severity == "error" for i in report.issues)
    new_approval_status = "BLOCKED" if still_blocked else (
        "PENDING" if old_approval_status == "BLOCKED" else old_approval_status
    )

    doc.parsed = {**parsed, "quality": report.as_dict()}
    doc.meta = {**(doc.meta or {}), "quality_status": report.status, "quality_score": report.score}

    approval.status = new_approval_status
    approval.payload = {
        **(approval.payload or {}),
        "quality_status": report.status,
        "blocking_issues": [
            {"code": i.code, "message": i.message, "where": i.where}
            for i in report.issues if i.severity == "error"
        ],
    }
    if new_approval_status != "BLOCKED" and approval.summary.startswith("⛔ BLOCKED — "):
        approval.summary = approval.summary.removeprefix("⛔ BLOCKED — ")
    elif new_approval_status == "BLOCKED" and not approval.summary.startswith("⛔"):
        approval.summary = f"⛔ BLOCKED — {approval.summary}"

    await audit.record(
        session, company_id=doc.company_id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.document_quality_rechecked", resource=doc.id,
        meta={
            "old_approval_status": old_approval_status, "new_approval_status": new_approval_status,
            "old_score": old_quality.get("score"), "new_score": report.score,
            "issue_codes": [i.code for i in report.issues],
        },
    )
    await session.commit()

    return _document_out(doc, approval)
