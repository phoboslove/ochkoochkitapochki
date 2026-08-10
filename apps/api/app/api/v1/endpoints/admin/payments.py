"""Admin records money that arrived outside the app (bank transfer, Kaspi
QR to a personal account, cash) — see ManualProvider. A real gateway later
adds itself as a second PaymentProvider; this route doesn't change."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, require_platform_admin
from app.services.audit.logger import AuditLogger
from app.services.billing.providers.manual import ManualProvider
from app.services.billing.repo import get_subscription_and_plan

router = APIRouter()
audit = AuditLogger()


class AddPaymentIn(BaseModel):
    amount: Decimal
    currency: str = "KZT"
    comment: str | None = None
    paid_at: datetime | None = None


@router.post("/companies/{company_id}/payments")
async def add_payment(
    company_id: str, body: AddPaymentIn,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        subscription, _plan = await get_subscription_and_plan(session, company_id)
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "company has no subscription")

    provider = ManualProvider()
    payment = await provider.create_payment(
        session, company_id=company_id, subscription_id=subscription.id,
        amount=body.amount, currency=body.currency,
        comment=body.comment, recorded_by=admin.id, paid_at=body.paid_at,
    )
    await audit.record(
        session, company_id=company_id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.payment_recorded",
        meta={"payment_id": payment.id, "amount": float(body.amount), "currency": body.currency},
    )
    await session.commit()
    return {"id": payment.id, "amount": float(payment.amount), "currency": payment.currency}
