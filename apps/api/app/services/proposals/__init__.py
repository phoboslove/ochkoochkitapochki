"""Pending-proposal store — pre-generation state machine.

Channels (Telegram, web, future WhatsApp) deposit a proposal here after
`propose_document` and reach back for it when the user confirms. The store
is the single source of truth: confirmation does NOT round-trip through
the LLM, which guarantees a "да" message from the same user fires
generation deterministically, even after webhook retries or short pauses.
"""
from app.services.proposals.store import (
    CONFIRM_PHRASES, CANCEL_PHRASES,
    ProposalStatus, is_confirmation, is_cancellation,
    create_pending, find_active, claim_for_generation,
    mark_completed, mark_cancelled, expire_stale,
)

__all__ = [
    "CONFIRM_PHRASES", "CANCEL_PHRASES",
    "ProposalStatus", "is_confirmation", "is_cancellation",
    "create_pending", "find_active", "claim_for_generation",
    "mark_completed", "mark_cancelled", "expire_stale",
]
