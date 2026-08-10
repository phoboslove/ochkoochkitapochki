"""Atomic monthly document counter — the plan's #1 enforcement test."""
import pytest

from app.services.billing.enforce import enforce_generation_allowed
from app.services.billing.exceptions import DocumentLimitExceededError
from app.services.billing.usage import get_current_usage


async def test_third_document_blocked_at_limit_two(session, seeded):
    company_id = seeded["company_id"]

    # Plan limit is 2 (see conftest's `seeded` fixture) — first two pass.
    await enforce_generation_allowed(session, company_id)
    await session.commit()
    await enforce_generation_allowed(session, company_id)
    await session.commit()

    assert await get_current_usage(session, company_id) == 2

    # Third is blocked, and the message carries used/limit for the UI.
    with pytest.raises(DocumentLimitExceededError) as exc_info:
        await enforce_generation_allowed(session, company_id)
    await session.rollback()
    assert exc_info.value.used == 2
    assert exc_info.value.limit == 2

    # The blocked attempt must not have consumed a slot — compensating
    # decrement + rollback should leave the counter exactly where it was.
    assert await get_current_usage(session, company_id) == 2
