"""Suspended subscriptions block generation — even with quota to spare."""
from datetime import datetime, timedelta

import pytest

from app.db.models import Subscription
from app.services.billing.enforce import enforce_generation_allowed
from app.services.billing.exceptions import SubscriptionSuspendedError
from app.services.billing.usage import get_current_usage


async def test_suspended_blocks_before_touching_the_counter(session, seeded):
    sub = await session.get(Subscription, seeded["subscription_id"])
    sub.status = "suspended"
    sub.period_end = datetime.utcnow() - timedelta(days=10)
    await session.commit()

    with pytest.raises(SubscriptionSuspendedError):
        await enforce_generation_allowed(session, seeded["company_id"])
    await session.rollback()

    # Suspended is checked before the atomic increment — a blocked company
    # should never see its counter move at all.
    assert await get_current_usage(session, seeded["company_id"]) == 0
