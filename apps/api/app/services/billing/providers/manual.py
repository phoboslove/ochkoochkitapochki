"""Manual payment provider — an admin confirms money arrived (bank
transfer, Kaspi QR paid to a personal account, cash) and records it. No
external API calls; the row itself is the source of truth."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Payment
from app.services.billing.providers.base import PaymentProvider


class ManualProvider(PaymentProvider):
    name = "manual"

    async def create_payment(
        self, session: AsyncSession, *, company_id: str, subscription_id: str,
        amount: Decimal, currency: str, **kwargs: Any,
    ) -> Payment:
        payment = Payment(
            id=f"pay_{uuid.uuid4().hex[:12]}", company_id=company_id,
            subscription_id=subscription_id, amount=amount, currency=currency,
            status="succeeded", method="manual",
            comment=kwargs.get("comment"), recorded_by=kwargs.get("recorded_by"),
            paid_at=kwargs.get("paid_at") or datetime.utcnow(),
        )
        session.add(payment)
        await session.flush()
        return payment

    async def handle_webhook(
        self, session: AsyncSession, *, raw_body: bytes, headers: dict[str, str],
    ) -> dict[str, Any]:
        raise NotImplementedError("manual provider has no webhooks — payments are admin-entered")

    async def check_status(self, session: AsyncSession, *, payment_id: str) -> str:
        payment = await session.get(Payment, payment_id)
        return payment.status if payment else "unknown"
