"""Atomic per-calendar-month document counter.

Deliberately not a COUNT(*) over AuditLog (the old `app/services/limits/
usage.py` pattern): that's a rolling 30-day scan, not calendar-month, and
two concurrent requests can both read a stale count before either commits —
under real concurrency (chat + Telegram + direct REST can all generate for
the same company at once) that lets a company blow through its limit. This
increments a single upserted row in one atomic statement and checks the
DB-returned post-increment value, so the limit genuinely cannot be raced.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageCounter
from app.services.billing.exceptions import DocumentLimitExceededError


def _current_period(now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    return now.strftime("%Y-%m")


async def _atomic_increment(session: AsyncSession, company_id: str, period: str) -> int:
    dialect = session.bind.dialect.name if session.bind is not None else "sqlite"
    now = datetime.utcnow()
    values = dict(
        id=f"uc_{uuid.uuid4().hex[:12]}", company_id=company_id, period=period,
        documents_count=1, updated_at=now,
    )
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    else:
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

    stmt = dialect_insert(UsageCounter).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["company_id", "period"],
        set_={"documents_count": UsageCounter.documents_count + 1, "updated_at": now},
    ).returning(UsageCounter.documents_count)
    result = await session.execute(stmt)
    return result.scalar_one()


async def _compensate_decrement(session: AsyncSession, company_id: str, period: str) -> None:
    await session.execute(
        update(UsageCounter)
        .where(UsageCounter.company_id == company_id, UsageCounter.period == period)
        .values(documents_count=UsageCounter.documents_count - 1, updated_at=datetime.utcnow()),
    )


async def increment_and_check(session: AsyncSession, company_id: str, limit: int) -> int:
    """Increments this month's counter and enforces `limit` atomically.
    Raises DocumentLimitExceededError (and compensates the increment back
    out) if the post-increment count exceeds the plan's limit."""
    period = _current_period()
    new_count = await _atomic_increment(session, company_id, period)
    if new_count > limit:
        await _compensate_decrement(session, company_id, period)
        raise DocumentLimitExceededError(used=new_count - 1, limit=limit)
    return new_count


async def get_current_usage(session: AsyncSession, company_id: str) -> int:
    """Read-only — current month's count without incrementing. Used by the
    client-facing usage display."""
    from sqlalchemy import select
    period = _current_period()
    count = await session.scalar(
        select(UsageCounter.documents_count).where(
            UsageCounter.company_id == company_id, UsageCounter.period == period,
        ),
    )
    return count or 0
