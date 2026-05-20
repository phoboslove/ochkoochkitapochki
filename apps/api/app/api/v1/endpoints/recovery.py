"""Workflow Recovery Center — failed events with retry / edit / escalate actions."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.db.models import AuditLog, Document, Invoice

router = APIRouter()


@router.get("")
async def list_failures(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return everything that needs operator attention.

    Sources:
      * audit log entries with action ending in `.failed` or `.send_failed`
      * documents in FAILED state
      * invoices in OVERDUE or PENDING_APPROVAL > 24h
    """
    rows = await session.scalars(
        select(AuditLog).where(
            AuditLog.company_id == user.company_id,
            or_(AuditLog.action.like("%failed%"), AuditLog.action.like("%denied%")),
        ).order_by(desc(AuditLog.at)).limit(100),
    )

    out: list[dict] = []
    for r in rows:
        kind = "document" if (r.resource or "").startswith("doc_") \
             else "invoice" if (r.resource or "").startswith("inv_") \
             else "system"
        out.append({
            "id": f"audit:{r.id}",
            "kind": kind,
            "action": r.action,
            "resource": r.resource,
            "at": r.at.isoformat(),
            "meta": r.meta,
            "actions": _actions_for(kind, r.action),
        })

    failed_docs = await session.scalars(
        select(Document).where(Document.company_id == user.company_id, Document.status == "FAILED"),
    )
    for d in failed_docs:
        out.append({
            "id": f"doc:{d.id}", "kind": "document", "action": "document.failed",
            "resource": d.id, "at": d.created_at.isoformat(),
            "meta": {"title": d.title, **(d.meta or {})},
            "actions": ["retry_ocr", "edit_fields", "escalate"],
        })

    overdue_invs = await session.scalars(
        select(Invoice).where(
            Invoice.company_id == user.company_id,
            Invoice.status.in_(("OVERDUE",)),
        ),
    )
    for i in overdue_invs:
        out.append({
            "id": f"inv:{i.id}", "kind": "invoice", "action": "invoice.overdue",
            "resource": i.id, "at": i.due_date.isoformat() if i.due_date else i.created_at.isoformat(),
            "meta": {"number": i.number, "total": str(i.total)},
            "actions": ["retry_send", "open_invoice", "escalate"],
        })

    out.sort(key=lambda r: r["at"], reverse=True)
    return out


def _actions_for(kind: str, action: str) -> list[str]:
    if kind == "document":
        return ["retry_ocr", "edit_fields", "escalate"]
    if kind == "invoice":
        return ["retry_send", "open_invoice", "escalate"]
    if action.startswith("whatsapp.send"):
        return ["retry_send", "escalate"]
    return ["escalate"]
