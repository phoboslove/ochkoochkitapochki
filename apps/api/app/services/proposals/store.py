"""Pending proposal store — CRUD + atomic state transitions.

Owner-only confirmation, TTL expiry, and a single-winner "claim" transition
that prevents double-fire on repeated confirmation messages.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PendingProposal


PROPOSAL_TTL = timedelta(minutes=20)


class ProposalStatus:
    AWAITING = "AWAITING_CONFIRMATION"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# ── Confirmation / cancellation phrase detection ────────────────────────────
#
# Tight set — we don't want to consume a user's free-form reply as
# confirmation. The phrase must BE the whole message (or start the message)
# to count. Edge cases like "да, но клиент другой" don't match — those
# correctly fall through to the LLM as a free-form edit.

CONFIRM_PHRASES = (
    "да", "ок", "ok", "yes", "y",
    "подтверждаю", "подтвержд", "подтверди",
    "создай", "создавай", "сделай", "сформируй",
    "confirm", "go", "погнали", "давай",
)
CANCEL_PHRASES = (
    "отмена", "отменить", "отмени", "стоп", "не надо", "не нужно",
    "cancel", "stop", "no", "нет", "abort",
)


def _matches(text: str, phrases: tuple[str, ...]) -> bool:
    t = (text or "").strip().lower().rstrip("!.?,")
    if not t:
        return False
    if t in phrases:
        return True
    # Allow leading phrase + optional comma + rest ("да, создай счёт" → confirm).
    for p in phrases:
        if t == p or t.startswith(p + " ") or t.startswith(p + ","):
            return True
    return False


def is_confirmation(text: str) -> bool:
    return _matches(text, CONFIRM_PHRASES)


def is_cancellation(text: str) -> bool:
    return _matches(text, CANCEL_PHRASES)


# ── CRUD ────────────────────────────────────────────────────────────────────

def _id() -> str:
    return f"pp_{uuid.uuid4().hex[:12]}"


async def create_pending(
    session: AsyncSession,
    *,
    company_id: str, user_id: str,
    channel: str,
    chat_id: str | None,
    conversation_id: str | None,
    kind: str,
    payload: dict[str, Any],
    template_id: str | None = None,
) -> PendingProposal:
    """Create a new AWAITING_CONFIRMATION proposal, expiring any prior active
    one for the same (company, user, channel, chat). One slot at a time —
    the latest propose wins."""
    # Expire any prior active proposal for this user+chat — keeps the
    # invariant that find_active() returns at most one row.
    await session.execute(
        update(PendingProposal)
        .where(
            PendingProposal.company_id == company_id,
            PendingProposal.user_id == user_id,
            PendingProposal.channel == channel,
            PendingProposal.chat_id == chat_id,
            PendingProposal.status == ProposalStatus.AWAITING,
        )
        .values(status=ProposalStatus.EXPIRED, decided_at=datetime.utcnow()),
    )
    proposal = PendingProposal(
        id=_id(),
        company_id=company_id, user_id=user_id,
        channel=channel, chat_id=chat_id, conversation_id=conversation_id,
        kind=kind,
        status=ProposalStatus.AWAITING,
        payload=payload,
        template_id=template_id,
        expires_at=datetime.utcnow() + PROPOSAL_TTL,
    )
    session.add(proposal)
    await session.flush()
    return proposal


async def find_active(
    session: AsyncSession,
    *,
    company_id: str, user_id: str,
    channel: str, chat_id: str | None,
) -> PendingProposal | None:
    """Return the user's active AWAITING_CONFIRMATION proposal, if any.

    Lazily expires the row if its TTL has passed — keeps the DB clean
    without a separate background sweeper for the demo MVP.
    """
    row = await session.scalar(
        select(PendingProposal).where(
            PendingProposal.company_id == company_id,
            PendingProposal.user_id == user_id,
            PendingProposal.channel == channel,
            PendingProposal.chat_id == chat_id,
            PendingProposal.status == ProposalStatus.AWAITING,
        ),
    )
    if not row:
        return None
    if row.expires_at < datetime.utcnow():
        row.status = ProposalStatus.EXPIRED
        row.decided_at = datetime.utcnow()
        await session.flush()
        return None
    return row


async def claim_for_generation(
    session: AsyncSession, *, proposal_id: str, user_id: str,
) -> PendingProposal | None:
    """Atomic AWAITING → GENERATING transition.

    Returns the proposal only when THIS call won the transition. A second
    concurrent confirm message will get None (no double-fire). Also enforces
    the owner-only invariant: a different user_id can't steal the
    proposal even if they share the same chat thread.
    """
    result = await session.execute(
        update(PendingProposal)
        .where(
            PendingProposal.id == proposal_id,
            PendingProposal.user_id == user_id,
            PendingProposal.status == ProposalStatus.AWAITING,
        )
        .values(status=ProposalStatus.GENERATING, decided_at=datetime.utcnow()),
    )
    if result.rowcount != 1:
        return None
    await session.flush()
    return await session.get(PendingProposal, proposal_id)


async def mark_completed(
    session: AsyncSession, *, proposal_id: str, document_id: str | None,
) -> None:
    await session.execute(
        update(PendingProposal)
        .where(PendingProposal.id == proposal_id)
        .values(status=ProposalStatus.COMPLETED,
                document_id=document_id,
                decided_at=datetime.utcnow()),
    )
    await session.flush()


async def mark_cancelled(
    session: AsyncSession, *, proposal_id: str, user_id: str,
) -> bool:
    """Owner-only cancel. Returns True iff this call actually flipped the row."""
    result = await session.execute(
        update(PendingProposal)
        .where(
            PendingProposal.id == proposal_id,
            PendingProposal.user_id == user_id,
            PendingProposal.status == ProposalStatus.AWAITING,
        )
        .values(status=ProposalStatus.CANCELLED, decided_at=datetime.utcnow()),
    )
    await session.flush()
    return result.rowcount == 1


async def expire_stale(session: AsyncSession) -> int:
    """Sweep expired AWAITING rows in bulk. Optional background hygiene."""
    result = await session.execute(
        update(PendingProposal)
        .where(
            PendingProposal.status == ProposalStatus.AWAITING,
            PendingProposal.expires_at < datetime.utcnow(),
        )
        .values(status=ProposalStatus.EXPIRED, decided_at=datetime.utcnow()),
    )
    await session.flush()
    return result.rowcount or 0
