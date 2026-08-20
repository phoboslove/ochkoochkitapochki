"""Fuzzy name matching for reference-data autofill — "Ромашка" in a chat
message should resolve to an existing "ТОО Ромашка" counterparty record
instead of spawning a duplicate.

Uses rapidfuzz's ``token_set_ratio``: built for "same words, different
order/extra tokens", which is exactly the shape of this problem once a
legal-form prefix (ТОО/ИП/АО/...) is stripped — a plain length-sensitive
ratio (e.g. stdlib ``difflib``) scores that comparison poorly without the
same normalization, and rapidfuzz's C++ backend is a light dependency
(no numpy/scipy) at the tenant-scale record counts this runs against.

No kind-awareness lives here on purpose: the same Client/Employee row is
shared across every document kind that mentions it, so "is this record
complete" is judged against one core field list per entity type, not a
per-kind one. Kind-specific required-ness is required_fields.py's job.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Employee

# >= this score: confident auto-match, autofill silently.
AUTO_MATCH_THRESHOLD = 82
# >= this score (but below AUTO_MATCH_THRESHOLD): still autofill, but flag
# low_confidence so the caller can surface it on the proposal card for the
# operator to confirm rather than silently trust either candidate.
POSSIBLE_MATCH_THRESHOLD = 65

_LEGAL_FORM_TOKENS = frozenset({
    "тоо", "too", "ип", "ao", "ао", "тов", "ооо", "оао", "зао", "чп",
    "llp", "llc", "inc", "ltd", "corp",
})

_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)

# Core completeness fields per entity type — plain Client/Employee model
# attribute names (not the "client_"/canonical schema keys required_fields.py
# uses; the caller maps between the two, see registry.py's autofill wiring).
COUNTERPARTY_CORE_FIELDS: tuple[str, ...] = ("bin", "address", "phone")
EMPLOYEE_CORE_FIELDS: tuple[str, ...] = ("iin", "position", "address")


def _normalize(name: str) -> str:
    tokens = [t for t in _TOKEN_RE.findall((name or "").lower()) if t not in _LEGAL_FORM_TOKENS]
    return " ".join(tokens)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class ResolvedEntity:
    record: Client | Employee
    created: bool
    match_score: float
    low_confidence: bool
    missing_fields: list[str]


def _missing_fields(record, keys: tuple[str, ...]) -> list[str]:
    return [k for k in keys if not getattr(record, k, None)]


async def best_match(
    session: AsyncSession, model: type[Client] | type[Employee],
    company_id: str, mentioned_name: str, name_attr: str,
) -> tuple[Client | Employee | None, float]:
    candidates = list(await session.scalars(
        select(model).where(model.company_id == company_id),
    ))
    if not candidates:
        return None, 0.0
    query = _normalize(mentioned_name)
    best, best_score = None, 0.0
    for c in candidates:
        score = fuzz.token_set_ratio(query, _normalize(getattr(c, name_attr)))
        if score > best_score:
            best, best_score = c, score
    return best, best_score


async def resolve_counterparty(
    session: AsyncSession, company_id: str, mentioned_name: str,
) -> ResolvedEntity:
    """Fuzzy-match ``mentioned_name`` against this company's Client rows.

    Auto-matches at >=82, flags low_confidence at 65-82, and creates a new
    stub record (just the name) below that — same behavior at every score
    band except the confidence flag, per the "always end up with a usable
    record, never block on an unmatched name" requirement.
    """
    name = (mentioned_name or "").strip()
    if not name:
        raise ValueError("mentioned_name is required")

    match, score = await best_match(session, Client, company_id, name, "name")
    if match and score >= POSSIBLE_MATCH_THRESHOLD:
        return ResolvedEntity(
            record=match, created=False, match_score=score,
            low_confidence=score < AUTO_MATCH_THRESHOLD,
            missing_fields=_missing_fields(match, COUNTERPARTY_CORE_FIELDS),
        )

    new = Client(id=_id("cl"), company_id=company_id, name=name)
    session.add(new)
    await session.flush()
    return ResolvedEntity(
        record=new, created=True, match_score=100.0, low_confidence=False,
        missing_fields=_missing_fields(new, COUNTERPARTY_CORE_FIELDS),
    )


async def resolve_employee(
    session: AsyncSession, company_id: str, mentioned_name: str,
) -> ResolvedEntity:
    """Same matching behavior as resolve_counterparty, against Employee."""
    name = (mentioned_name or "").strip()
    if not name:
        raise ValueError("mentioned_name is required")

    match, score = await best_match(session, Employee, company_id, name, "full_name")
    if match and score >= POSSIBLE_MATCH_THRESHOLD:
        return ResolvedEntity(
            record=match, created=False, match_score=score,
            low_confidence=score < AUTO_MATCH_THRESHOLD,
            missing_fields=_missing_fields(match, EMPLOYEE_CORE_FIELDS),
        )

    new = Employee(id=_id("emp"), company_id=company_id, full_name=name)
    session.add(new)
    await session.flush()
    return ResolvedEntity(
        record=new, created=True, match_score=100.0, low_confidence=False,
        missing_fields=_missing_fields(new, EMPLOYEE_CORE_FIELDS),
    )
