"""Plan-aware usage gate — enforced before uploads, invites, and invoice
ledger entries. Sourced from the DB-backed Plan/Subscription (see
app/services/billing/repo.py), not a hardcoded dict — pricing/limits are
now admin-editable without a deploy.

Counters here still come from the audit log (rolling 30-day window). This
is a *different* quota from the generation monthly-document counter in
app/services/billing/usage.py, which is calendar-month + atomically
incremented specifically for AI-generated documents (see that module's
docstring for why the two aren't the same mechanism).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Plan
from app.services.billing.repo import get_subscription_and_plan


class QuotaExceeded(Exception):
    def __init__(self, feature: str, used: int, limit: int):
        super().__init__(f"{feature} quota exceeded ({used}/{limit})")
        self.feature, self.used, self.limit = feature, used, limit


async def _plan_for(session: AsyncSession, company_id: str) -> Plan | None:
    try:
        _sub, plan = await get_subscription_and_plan(session, company_id)
        return plan
    except LookupError:
        return None


async def _count_actions(session: AsyncSession, company_id: str, action: str) -> int:
    cutoff = datetime.utcnow() - timedelta(days=30)
    return (await session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.company_id == company_id,
            AuditLog.action == action,
            AuditLog.at >= cutoff,
        ),
    )) or 0


async def assert_can_create_invoice(session: AsyncSession, company_id: str) -> None:
    plan = await _plan_for(session, company_id)
    if plan is None:
        return  # no subscription row is a data-integrity bug, not a billing block
    # Invoice ledger entries share the document budget — the new Plan
    # schema doesn't carry a separate invoices_per_month figure.
    limit = plan.limit_documents_per_month
    used = await _count_actions(session, company_id, "invoice.create_draft")
    if used >= limit:
        raise QuotaExceeded("invoices_per_month", used, limit)


async def assert_can_upload_document(session: AsyncSession, company_id: str) -> None:
    plan = await _plan_for(session, company_id)
    if plan is None:
        return
    limit = plan.limit_documents_per_month
    used = await _count_actions(session, company_id, "document.upload")
    if used >= limit:
        raise QuotaExceeded("documents_per_month", used, limit)


async def assert_can_invite_seat(session: AsyncSession, company_id: str) -> None:
    from app.db.models import User, Invitation
    plan = await _plan_for(session, company_id)
    if plan is None:
        return
    seats = (await session.scalar(
        select(func.count(User.id)).where(User.company_id == company_id, User.active == True),  # noqa: E712
    )) or 0
    pending = (await session.scalar(
        select(func.count(Invitation.id)).where(
            Invitation.company_id == company_id, Invitation.status == "PENDING",
        ),
    )) or 0
    if seats + pending >= plan.limit_users:
        raise QuotaExceeded("seats", seats + pending, plan.limit_users)
