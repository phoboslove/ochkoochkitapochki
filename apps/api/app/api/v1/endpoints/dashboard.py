"""Lightweight dashboard summary — counts via SQL COUNT(*), not by fetching
every row. The dashboard previously loaded the company's entire documents
and approvals lists just to compute this-month counts and show the last 5,
which made initial load unusably slow for any account with real history."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.approvals import _serialize as _serialize_approval
from app.api.v1.endpoints.documents import _serialize as _serialize_document
from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.db.models import Approval, Document

router = APIRouter()

_RECENT_LIMIT = 5


@router.get("/summary")
async def dashboard_summary(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    company_id = user.company_id
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    generated_this_month = await session.scalar(
        select(func.count(Document.id)).where(
            Document.company_id == company_id, Document.status == "GENERATED",
            Document.created_at >= month_start,
        ),
    )
    pending_this_month = await session.scalar(
        select(func.count(Approval.id)).where(
            Approval.company_id == company_id, Approval.status == "PENDING",
            Approval.created_at >= month_start,
        ),
    )
    blocked_this_month = await session.scalar(
        select(func.count(Approval.id)).where(
            Approval.company_id == company_id, Approval.status == "BLOCKED",
            Approval.created_at >= month_start,
        ),
    )

    recent_documents = await session.scalars(
        select(Document).where(Document.company_id == company_id)
        .order_by(Document.created_at.desc()).limit(_RECENT_LIMIT),
    )
    recent_pending_approvals = await session.scalars(
        select(Approval).where(Approval.company_id == company_id, Approval.status == "PENDING")
        .order_by(Approval.created_at.desc()).limit(_RECENT_LIMIT),
    )

    return {
        "documents_generated_this_month": generated_this_month or 0,
        "approvals_pending_this_month": pending_this_month or 0,
        "approvals_blocked_this_month": blocked_this_month or 0,
        "recent_documents": [_serialize_document(d) for d in recent_documents],
        "recent_pending_approvals": [_serialize_approval(a) for a in recent_pending_approvals],
    }
