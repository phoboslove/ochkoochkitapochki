"""Client-facing billing read endpoint + payment-webhook scaffold.

The webhook route is a real, routable endpoint with signature-validation
shape already in place, but returns 501 — no live gateway exists yet (see
app/services/billing/providers/). Adding Kaspi/CloudPayments later means
implementing PaymentProvider.handle_webhook for that provider and wiring it
into KNOWN_PROVIDERS below; this route doesn't change.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.services.billing.repo import get_subscription_and_plan
from app.services.billing.status import refresh_status
from app.services.billing.usage import get_current_usage

router = APIRouter()

KNOWN_PROVIDERS = {"manual", "kaspi", "cloudpayments"}


@router.get("/subscription")
async def get_my_subscription(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        subscription, plan = await get_subscription_and_plan(session, user.company_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no subscription on record")
    subscription = await refresh_status(session, subscription)
    await session.commit()

    used = await get_current_usage(session, user.company_id)
    now = datetime.utcnow()
    grace_end = subscription.period_end + timedelta(days=subscription.grace_period_days)
    days_left = (subscription.period_end - now).days
    grace_days_left = (grace_end - now).days

    return {
        "plan": {
            "code": plan.code, "name": plan.name,
            "price_amount": float(plan.price_amount), "price_currency": plan.price_currency,
            "billing_period": plan.billing_period,
        },
        "status": subscription.status,
        "period_start": subscription.period_start.isoformat(),
        "period_end": subscription.period_end.isoformat(),
        "days_until_period_end": days_left,
        "grace_period_days": subscription.grace_period_days,
        "days_until_suspend": grace_days_left if subscription.status == "past_due" else None,
        "renewal_method": subscription.renewal_method,
        "usage": {
            "documents_used": used, "documents_limit": plan.limit_documents_per_month,
        },
        "limits": {
            "documents_per_month": plan.limit_documents_per_month,
            "users": plan.limit_users, "templates": plan.limit_templates,
        },
    }


@router.get("/payments")
async def list_my_payments(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    from sqlalchemy import select, desc
    from app.db.models import Payment
    rows = await session.scalars(
        select(Payment).where(Payment.company_id == user.company_id).order_by(desc(Payment.created_at)),
    )
    return [
        {
            "id": p.id, "amount": float(p.amount), "currency": p.currency,
            "status": p.status, "method": p.method, "comment": p.comment,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "created_at": p.created_at.isoformat(),
        }
        for p in rows
    ]


@router.post("/webhook/{provider}")
async def payment_webhook(provider: str, request: Request) -> dict:
    if provider not in KNOWN_PROVIDERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown provider: {provider!r}")
    # Scaffold: raw body + signature header are already read here so a real
    # implementation only needs to add verification + processing, not wire
    # up the route from scratch.
    _raw_body = await request.body()
    _signature = request.headers.get("x-signature") or request.headers.get("x-webhook-signature")
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        f"{provider} payment webhooks are not implemented yet — payments are recorded manually via /admin.",
    )
