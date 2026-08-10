"""Payment provider seam. `ManualProvider` is the only implementation today
(admin records "money arrived" by hand). A real gateway (Kaspi,
CloudPayments) becomes a second implementation of this interface — nothing
in enforcement, the pipeline, or the admin UI needs to change; only the
provider registry (`get_provider`) gains an entry.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Payment


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def create_payment(
        self, session: AsyncSession, *, company_id: str, subscription_id: str,
        amount: Decimal, currency: str, **kwargs: Any,
    ) -> Payment:
        """Record/initiate a payment. For gateway providers this would call
        out to the external API; for ManualProvider it just writes the row —
        the money has already changed hands by the time an admin clicks
        "add payment"."""

    @abstractmethod
    async def handle_webhook(
        self, session: AsyncSession, *, raw_body: bytes, headers: dict[str, str],
    ) -> dict[str, Any]:
        """Verify + process an inbound gateway webhook. Raises for unknown
        signatures — see app/api/v1/endpoints/billing.py for the route."""

    @abstractmethod
    async def check_status(self, session: AsyncSession, *, payment_id: str) -> str:
        """Return the current status of a previously created payment."""


def get_provider(name: str) -> PaymentProvider:
    if name == "manual":
        from app.services.billing.providers.manual import ManualProvider
        return ManualProvider()
    raise ValueError(f"unknown payment provider: {name!r}")
