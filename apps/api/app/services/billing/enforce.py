"""The one function GenerationPipeline.generate() calls before doing any
real work. Combines the two independent checks (status, monthly count)
into a single call so there's exactly one enforcement entry point shared
by every caller that reaches the pipeline (AI tool, direct REST endpoint,
Telegram) — see pipeline.py for why this is the single choke point.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.billing.exceptions import SubscriptionSuspendedError
from app.services.billing.repo import get_subscription_and_plan
from app.services.billing.status import refresh_status
from app.services.billing.usage import increment_and_check


async def enforce_generation_allowed(session: AsyncSession, company_id: str) -> None:
    subscription, plan = await get_subscription_and_plan(session, company_id)
    subscription = await refresh_status(session, subscription)
    if subscription.status == "suspended":
        raise SubscriptionSuspendedError(company_id, subscription.period_end)
    await increment_and_check(session, company_id, plan.limit_documents_per_month)
