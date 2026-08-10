"""FastAPI dependency gating endpoints that don't go through
GenerationPipeline but still cost money or create data when the company is
suspended: AI chat (every turn burns OpenAI tokens even without a tool
call) and template uploads. past_due passes through — only `suspended`
blocks. Reading existing data is never gated (see /billing/subscription,
which is intentionally NOT behind this dependency)."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.services.billing.repo import get_subscription_and_plan
from app.services.billing.status import refresh_status


async def require_active_subscription(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    try:
        subscription, _plan = await get_subscription_and_plan(session, user.company_id)
    except LookupError:
        # No subscription row is a data-integrity bug, not a billing block —
        # never punish a real user for a missing row they can't fix.
        return user
    subscription = await refresh_status(session, subscription)
    if subscription.status == "suspended":
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "Подписка приостановлена — оплаченный период и льготный срок истекли. "
            "Продлите подписку, чтобы возобновить работу.",
        )
    return user
