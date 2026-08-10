"""Shared subscription/plan lookups — used by enforcement, admin, and the
client-facing billing endpoint so there's exactly one way to resolve
"what plan/subscription does this company have"."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Plan, Subscription

TRIAL_PLAN_CODE = "trial"
TRIAL_PERIOD_DAYS = 30


async def get_subscription(session: AsyncSession, company_id: str) -> Subscription | None:
    return await session.scalar(select(Subscription).where(Subscription.company_id == company_id))


async def get_plan(session: AsyncSession, plan_id: str) -> Plan | None:
    return await session.get(Plan, plan_id)


async def get_plan_by_code(session: AsyncSession, code: str) -> Plan | None:
    return await session.scalar(select(Plan).where(Plan.code == code))


async def get_subscription_and_plan(
    session: AsyncSession, company_id: str,
) -> tuple[Subscription, Plan]:
    """Raises LookupError if the company has no subscription or the
    subscription references a missing plan — both indicate a data-integrity
    bug (every company must have a subscription; see create_trial_subscription)
    rather than a normal "no subscription yet" case to swallow silently."""
    sub = await get_subscription(session, company_id)
    if sub is None:
        raise LookupError(f"company {company_id} has no subscription")
    plan = await get_plan(session, sub.plan_id)
    if plan is None:
        raise LookupError(f"subscription {sub.id} references missing plan {sub.plan_id}")
    return sub, plan


async def create_trial_subscription(session: AsyncSession, company_id: str) -> Subscription:
    """Every company must have exactly one subscription from the moment it
    exists — called from registration and from the admin create-company
    flow, so enforcement never has to handle a "no subscription" company."""
    plan = await get_plan_by_code(session, TRIAL_PLAN_CODE)
    if plan is None:
        raise LookupError("trial plan not seeded — run migrations")
    now = datetime.utcnow()
    sub = Subscription(
        id=f"sub_{uuid.uuid4().hex[:12]}", company_id=company_id, plan_id=plan.id,
        status="trialing", period_start=now, period_end=now + timedelta(days=TRIAL_PERIOD_DAYS),
        renewal_method="manual", grace_period_days=5,
    )
    session.add(sub)
    await session.flush()
    return sub
