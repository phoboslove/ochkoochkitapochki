"""Self-healing status transitions — no scheduler, just refresh-on-touch."""
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import AuditLog, Subscription
from app.services.billing.status import effective_status, refresh_status


async def test_past_due_within_grace(session, seeded):
    sub = await session.get(Subscription, seeded["subscription_id"])
    sub.period_end = datetime.utcnow() - timedelta(days=1)  # 1 day late, 5-day grace
    await session.commit()

    assert effective_status(sub, datetime.utcnow()) == "past_due"


async def test_suspended_after_grace_and_audit_logged(session, seeded):
    sub = await session.get(Subscription, seeded["subscription_id"])
    sub.status = "past_due"
    sub.period_end = datetime.utcnow() - timedelta(days=10)  # past the 5-day grace
    await session.commit()

    updated = await refresh_status(session, sub)
    assert updated.status == "suspended"
    assert updated.suspended_at is not None

    rows = list(await session.scalars(
        select(AuditLog).where(
            AuditLog.company_id == seeded["company_id"],
            AuditLog.action == "subscription.status_changed",
        ),
    ))
    assert len(rows) == 1
    assert rows[0].meta["from"] == "past_due"
    assert rows[0].meta["to"] == "suspended"


async def test_reactivation_on_period_extension(session, seeded):
    sub = await session.get(Subscription, seeded["subscription_id"])
    sub.status = "suspended"
    sub.period_end = datetime.utcnow() - timedelta(days=10)
    await session.commit()

    # Admin extends the period — status should self-heal to "active", not
    # stay stuck on "suspended" or revert to "trialing".
    sub.period_end = datetime.utcnow() + timedelta(days=30)
    await session.commit()
    updated = await refresh_status(session, sub)
    assert updated.status == "active"
    assert updated.suspended_at is None
