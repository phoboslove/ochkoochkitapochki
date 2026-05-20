"""Plan-aware usage gate — enforced before AI tools, uploads, and invoice creation.

Counters come from the audit log (single source of truth, no extra table).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Company
from app.services.plans.gate import limits_for


class QuotaExceeded(Exception):
    def __init__(self, feature: str, used: int, limit: int):
        super().__init__(f"{feature} quota exceeded ({used}/{limit})")
        self.feature, self.used, self.limit = feature, used, limit


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
    company = await session.get(Company, company_id)
    limits = limits_for(company.plan if company else "free")
    used = await _count_actions(session, company_id, "invoice.create_draft")
    if used >= limits.invoices_per_month:
        raise QuotaExceeded("invoices_per_month", used, limits.invoices_per_month)


async def assert_can_upload_document(session: AsyncSession, company_id: str) -> None:
    company = await session.get(Company, company_id)
    limits = limits_for(company.plan if company else "free")
    used = await _count_actions(session, company_id, "document.upload")
    if used >= limits.documents_per_month:
        raise QuotaExceeded("documents_per_month", used, limits.documents_per_month)


async def assert_can_invite_seat(session: AsyncSession, company_id: str) -> None:
    from app.db.models import User, Invitation
    company = await session.get(Company, company_id)
    limits = limits_for(company.plan if company else "free")
    seats = (await session.scalar(
        select(func.count(User.id)).where(User.company_id == company_id, User.active == True),  # noqa: E712
    )) or 0
    pending = (await session.scalar(
        select(func.count(Invitation.id)).where(
            Invitation.company_id == company_id, Invitation.status == "PENDING",
        ),
    )) or 0
    if seats + pending >= limits.seats:
        raise QuotaExceeded("seats", seats + pending, limits.seats)
