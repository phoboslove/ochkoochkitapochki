"""Platform dashboard — cross-tenant metrics for running the business."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, require_platform_admin
from app.db.models import Company, Plan, Subscription, UsageCounter

router = APIRouter()

# The dedicated non-customer company holding platform-admin accounts (see
# migration 0003) — never counted as a real tenant.
_PLATFORM_COMPANY_ID = "c_platform"


@router.get("/dashboard")
async def dashboard(
    _admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    status_rows = await session.execute(
        select(Subscription.status, func.count(Subscription.id))
        .where(Subscription.company_id != _PLATFORM_COMPANY_ID)
        .group_by(Subscription.status),
    )
    by_status = {s: n for s, n in status_rows.all()}
    total_companies = await session.scalar(
        select(func.count(Company.id)).where(Company.id != _PLATFORM_COMPANY_ID),
    ) or 0

    period = datetime.utcnow().strftime("%Y-%m")
    docs_this_month = await session.scalar(
        select(func.coalesce(func.sum(UsageCounter.documents_count), 0)).where(
            UsageCounter.period == period,
        ),
    ) or 0

    # MRR — sum of price_amount for subscriptions actively paying (status=active).
    mrr = await session.scalar(
        select(func.coalesce(func.sum(Plan.price_amount), 0))
        .select_from(Subscription).join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.status == "active"),
    ) or 0

    top_rows = await session.execute(
        select(UsageCounter.company_id, Company.name, UsageCounter.documents_count)
        .join(Company, Company.id == UsageCounter.company_id)
        .where(UsageCounter.period == period)
        .order_by(UsageCounter.documents_count.desc())
        .limit(10),
    )
    top_companies = [
        {"company_id": cid, "company_name": name, "documents_this_month": count}
        for cid, name, count in top_rows.all()
    ]

    return {
        "companies": {
            "total": total_companies,
            "active": by_status.get("active", 0),
            "trialing": by_status.get("trialing", 0),
            "past_due": by_status.get("past_due", 0),
            "suspended": by_status.get("suspended", 0),
            "cancelled": by_status.get("cancelled", 0),
        },
        "documents_this_month": docs_this_month,
        "mrr": float(mrr),
        "mrr_currency": "KZT",
        "top_companies": top_companies,
    }
