"""Manual (admin) suspend must stick — unlike the natural past_due->suspended
transition, it must not self-heal back to active just because period_end
hasn't been reached yet. Regression test for a bug found live in prod: an
admin-suspended company with a fresh trial kept generating documents because
effective_status() assumed any suspended-with-future-period_end state meant
"someone renewed it"."""
from datetime import datetime, timedelta

import pytest

from app.db.models import Subscription
from app.services.billing.enforce import enforce_generation_allowed
from app.services.billing.exceptions import SubscriptionSuspendedError
from app.services.billing.status import effective_status, refresh_status


async def test_manual_suspend_survives_future_period_end(session, seeded):
    sub = await session.get(Subscription, seeded["subscription_id"])
    assert sub.period_end > datetime.utcnow()  # still well within the trial/paid period
    sub.status = "suspended"
    sub.manually_suspended = True
    sub.suspended_at = datetime.utcnow()
    await session.commit()

    assert effective_status(sub, datetime.utcnow()) == "suspended"

    # Generation must be blocked immediately...
    with pytest.raises(SubscriptionSuspendedError):
        await enforce_generation_allowed(session, seeded["company_id"])
    await session.rollback()

    # ...and stay blocked after the status is re-read/refreshed, not silently
    # revert to active the way a natural suspend-then-renew would. Re-fetch
    # rather than reuse `sub` — rollback() expires it, and touching a stale
    # instance's attributes outside an await triggers a lazy-load that
    # crashes async SQLAlchemy with a MissingGreenlet error.
    sub = await session.get(Subscription, seeded["subscription_id"])
    refreshed = await refresh_status(session, sub)
    assert refreshed.status == "suspended"

    with pytest.raises(SubscriptionSuspendedError):
        await enforce_generation_allowed(session, seeded["company_id"])
