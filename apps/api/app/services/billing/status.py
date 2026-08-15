"""Self-healing subscription status — no scheduler needed.

Same pattern already used by PendingProposal in this codebase (see its
docstring: "EXPIRED (TTL passed, lazily checked)") — status is derived from
a timestamp and persisted back the next time anything touches the
subscription, rather than driven by a background job. `refresh_status` is
called at every enforcement/read checkpoint (generation, /billing/subscription,
admin views), so a company's status updates itself within one request of
crossing a boundary — no cron required.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Subscription
from app.services.audit.logger import AuditLogger

_TERMINAL_UNCHANGED = {"cancelled"}


def effective_status(subscription: Subscription, now: datetime) -> str:
    """Pure function — no DB access, easy to unit test."""
    if subscription.status in _TERMINAL_UNCHANGED:
        return subscription.status

    # An admin-initiated suspend is sticky: it must not self-heal back to
    # active just because period_end hasn't been reached yet (that's the
    # normal state for a manual suspend — it doesn't touch period_end at
    # all). Only an explicit reactivate() call clears manually_suspended.
    if subscription.status == "suspended" and subscription.manually_suspended:
        return "suspended"

    grace_end = subscription.period_end + timedelta(days=subscription.grace_period_days)

    if now <= subscription.period_end:
        # Still within the paid/trial period. If it was previously past_due
        # or suspended, period_end having moved forward means someone
        # renewed it (admin extended it / recorded a payment) — that's a
        # paid reactivation, not a trial.
        if subscription.status in ("past_due", "suspended"):
            return "active"
        return subscription.status  # trialing or active, unchanged

    if now <= grace_end:
        return "past_due"

    return "suspended"


async def refresh_status(session: AsyncSession, subscription: Subscription) -> Subscription:
    """Persist the derived status if it differs, with an audit trail entry
    on every transition. Safe to call on every request — it's a no-op read
    when nothing has changed.

    Commits immediately on a transition rather than just flushing: this is
    called from inside enforcement (e.g. right before a blocked generation
    attempt raises), and a plain flush would get silently rolled back along
    with the rest of that request's transaction when the caller's session
    closes on the exception. The status transition is an independent fact
    (time passed a boundary) that must survive regardless of what the
    triggering request does next.
    """
    now = datetime.utcnow()
    new_status = effective_status(subscription, now)
    if new_status != subscription.status:
        old_status = subscription.status
        subscription.status = new_status
        if new_status == "suspended" and subscription.suspended_at is None:
            subscription.suspended_at = now
        elif new_status in ("active", "trialing"):
            subscription.suspended_at = None
        await AuditLogger().record(
            session, company_id=subscription.company_id, actor_type="system",
            action="subscription.status_changed",
            meta={"from": old_status, "to": new_status,
                  "period_end": subscription.period_end.isoformat()},
        )
        await session.commit()
    return subscription
