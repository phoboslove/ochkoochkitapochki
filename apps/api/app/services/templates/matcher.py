"""Deterministic + semantic template selection.

Score formula (per candidate):
  +40  kind matches
  +20  industry matches
  +10  language matches
  +10  is_default
  +25  cap on usage_frequency  (0.4 * success_count)
  +12  VERIFIED
  +5   confidence ≥ 0.8
  +0..40 semantic_match against the user query
  -50  legacy .doc/.xls

Tie-break: most recent successful render.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Template
from app.services.templates.semantic import semantic_score


@dataclass
class CandidateScore:
    template: Template
    score: int
    breakdown: dict[str, int]
    matched_terms: list[str]


@dataclass
class MatchResult:
    template: Template | None
    score: int
    breakdown: dict[str, int]
    matched_terms: list[str]
    alternatives: list[tuple[Template, int]]
    reason: str
    needs_review: list[Template]
    confident: bool        # True when winner ≥ 70 and beats #2 by ≥ 15
    ambiguous: bool        # True when top-2 are within 10 points and ≥ 2 candidates


async def match_best(
    session: AsyncSession, *, company_id: str,
    kind: str | None = None,
    industry: str | None = None, language: str | None = None,
    query: str | None = None,
) -> MatchResult:
    rows = list(await session.scalars(
        select(Template).where(
            Template.company_id == company_id,
            Template.status != "ARCHIVED",
        ).order_by(desc(Template.last_render_at)),
    ))
    # When no explicit kind, score across the whole library.
    in_scope = [t for t in rows if (kind is None or t.kind == kind)]
    needs_review = [t for t in in_scope if t.status != "VERIFIED"]
    candidates  = [t for t in in_scope if t.status == "VERIFIED"]

    scored: list[CandidateScore] = []
    for t in candidates:
        b: dict[str, int] = {}
        s = 0
        if kind and t.kind == kind:                       s += 40; b["kind"] = 40
        if industry and t.industry == industry:           s += 20; b["industry"] = 20
        if language and t.language == language:           s += 10; b["language"] = 10
        if t.is_default:                                   s += 10; b["default"] = 10
        usage = min(25, int(0.4 * _success_count(t)))
        if usage:                                          s += usage; b["usage"] = usage
        s += 12; b["verified"] = 12
        if (t.confidence or 0) >= 0.8:                    s += 5;  b["confidence"] = 5
        if t.format in ("doc", "xls"):                    s -= 50; b["legacy_penalty"] = -50

        matched_terms: list[str] = []
        if query:
            sem_score, matched_terms = semantic_score(
                (t.detected_fields or {}).get("semantic"), query=query,
            )
            if sem_score:
                s += sem_score; b["semantic"] = sem_score
        scored.append(CandidateScore(t, s, b, matched_terms))

    if not scored:
        reason = (
            f"No VERIFIED template for kind={kind or 'any'}. "
            f"{len(needs_review)} candidate(s) await mapping confirmation."
            if needs_review else
            f"No template uploaded for kind={kind or 'any'}. Using built-in HTML fallback."
        )
        return MatchResult(template=None, score=0, breakdown={}, matched_terms=[],
                            alternatives=[], reason=reason,
                            needs_review=needs_review[:5],
                            confident=False, ambiguous=False)

    scored.sort(key=lambda c: c.score, reverse=True)
    top = scored[0]
    runner = scored[1].score if len(scored) > 1 else 0
    confident = top.score >= 70 and (top.score - runner) >= 15
    ambiguous = len(scored) > 1 and (top.score - runner) <= 10 and top.score >= 50

    bits = []
    if top.breakdown.get("kind"):     bits.append(f"kind matches")
    if top.breakdown.get("industry"): bits.append(f"industry {top.template.industry}")
    if top.matched_terms:             bits.append(f"semantic terms: {', '.join(top.matched_terms[:4])}")
    if top.breakdown.get("usage"):    bits.append(f"used {_success_count(top.template)}× successfully")
    if top.breakdown.get("confidence"): bits.append("high mapping confidence")

    reason = (
        f"Selected '{top.template.name}' · score {top.score} — "
        + ("; ".join(bits) if bits else "VERIFIED template")
    )
    return MatchResult(
        template=top.template, score=top.score,
        breakdown=top.breakdown, matched_terms=top.matched_terms,
        alternatives=[(c.template, c.score) for c in scored[1:6]],
        reason=reason, needs_review=needs_review[:5],
        confident=confident, ambiguous=ambiguous,
    )


def _success_count(t: Template) -> int:
    df = t.detected_fields or {}
    usage = df.get("usage") or {}
    return int(usage.get("success_count") or 0)


def bump_success(t: Template) -> None:
    df = dict(t.detected_fields or {})
    usage = dict(df.get("usage") or {})
    usage["success_count"] = _success_count(t) + 1
    df["usage"] = usage
    t.detected_fields = df
