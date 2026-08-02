"""Per-template operational reliability — Priority 5.

Aggregates real production signal recorded by the pipeline:
  * `audit_logs` rows with action='document.generated'   → render outcomes
  * `audit_logs` rows with action='approval.blocked'     → approval blocks
  * `audit_logs` rows with action='approval.request'     → approval requests
  * `Document.parsed.quality`                            → quality scores

Output is a numeric `operational_score` (0–100) plus the underlying signals so
the operator UI can show "why this template is reliable / unreliable."

The matcher (`templates.matcher.match_best`) reads this score and biases
selection toward templates that *actually work in production*, not just
templates that score well semantically.

DESIGN NOTES:
  * Cold-start: templates with zero render history return a neutral score
    (70). This avoids permanently exiling new uploads.
  * Window: the last ``LOOKBACK_RENDERS`` rendered documents are used, so a
    template that *used* to fail but has been fixed recovers within one
    window of renders.
  * Cheap: a single grouped query over audit_logs + a small fetch of recent
    Document rows. No table writes; recomputed on demand.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Document, Template

LOOKBACK_RENDERS = 20             # window for the rolling reliability metric
COLD_START_SCORE = 70             # neutral score for templates with no history
MAX_OPERATIONAL_BONUS = 20        # matcher additive cap


@dataclass
class TemplateReliability:
    template_id: str
    operational_score: int            # 0..100 — drives matcher
    sample_size: int                   # number of renders in the window
    cold_start: bool                   # True when sample_size == 0
    render_success_rate: float        # 0..1 (no fallback + no exception)
    fallback_rate: float              # 0..1
    avg_quality_score: float          # 0..100
    blocked_approval_rate: float      # 0..1
    avg_render_ms: int                # ms
    last_failed_at: str | None        # ISO timestamp of last error, if any
    last_succeeded_at: str | None
    drivers: list[str] = field(default_factory=list)  # human-readable why-this-score lines

    def matcher_bonus(self) -> int:
        """Scale operational_score into the matcher score range.

        Templates at the cold-start neutral (70) contribute 0; perfectly
        reliable templates contribute MAX_OPERATIONAL_BONUS. Templates below
        50 get a NEGATIVE bonus so the matcher actively demotes them.
        """
        if self.cold_start:
            return 0
        # Linear map: 50→-10, 70→0, 100→+20.
        return int(round((self.operational_score - 70) / 30 * MAX_OPERATIONAL_BONUS))

    def as_dict(self) -> dict[str, Any]:
        return {
            "template_id":           self.template_id,
            "operational_score":     self.operational_score,
            "matcher_bonus":         self.matcher_bonus(),
            "sample_size":           self.sample_size,
            "cold_start":            self.cold_start,
            "render_success_rate":   round(self.render_success_rate, 3),
            "fallback_rate":         round(self.fallback_rate, 3),
            "avg_quality_score":     round(self.avg_quality_score, 1),
            "blocked_approval_rate": round(self.blocked_approval_rate, 3),
            "avg_render_ms":         self.avg_render_ms,
            "last_failed_at":        self.last_failed_at,
            "last_succeeded_at":     self.last_succeeded_at,
            "drivers":               self.drivers,
        }


# ── Aggregator ──────────────────────────────────────────────────────────────

async def compute_reliability(
    session: AsyncSession, *, template_id: str, company_id: str,
) -> TemplateReliability:
    """Compute reliability for one template against this company's history."""
    # 1. Recent document.generated events that selected this template.
    #    The pipeline records `template_id` in meta — we filter in SQL via JSON.
    #    SQLite + Postgres both support `JSON_EXTRACT` semantics via SA's `.op('->>')`,
    #    but the cheapest portable path is to filter in Python over a bounded
    #    set of recent rows (LOOKBACK_RENDERS * 4 to give headroom).
    rows = list(await session.scalars(
        select(AuditLog).where(
            AuditLog.company_id == company_id,
            AuditLog.action == "document.generated",
        ).order_by(desc(AuditLog.at)).limit(LOOKBACK_RENDERS * 4),
    ))
    events = [r for r in rows if (r.meta or {}).get("template_id") == template_id]
    events = events[:LOOKBACK_RENDERS]

    if not events:
        return TemplateReliability(
            template_id=template_id, operational_score=COLD_START_SCORE,
            sample_size=0, cold_start=True,
            render_success_rate=0.0, fallback_rate=0.0,
            avg_quality_score=0.0, blocked_approval_rate=0.0,
            avg_render_ms=0, last_failed_at=None, last_succeeded_at=None,
            drivers=["No render history yet — using neutral cold-start score."],
        )

    n = len(events)
    quality_scores  = [int((e.meta or {}).get("quality_score") or 0) for e in events]
    statuses        = [(e.meta or {}).get("quality_status") for e in events]
    fallbacks       = [bool((e.meta or {}).get("fallback_used") or
                              (e.meta or {}).get("fallback", {}).get("used"))
                         for e in events]
    blocked_count   = sum(1 for s in statuses if s == "blocked")
    fallback_count  = sum(1 for f in fallbacks if f)
    success_count   = sum(1 for s, f in zip(statuses, fallbacks)
                            if s in ("ok", "warning") and not f)

    avg_quality = sum(quality_scores) / n if n else 0.0
    fallback_rate = fallback_count / n
    blocked_rate = blocked_count / n
    success_rate = success_count / n

    # 2. Render durations — read from Document.parsed where present.
    avg_ms = 0
    doc_rows = list(await session.scalars(
        select(Document).where(
            Document.company_id == company_id,
            Document.status == "GENERATED",
        ).order_by(desc(Document.created_at)).limit(LOOKBACK_RENDERS * 4),
    ))
    matching_docs = [
        d for d in doc_rows
        if ((d.parsed or {}).get("template") or {}).get("id") == template_id
    ][:LOOKBACK_RENDERS]
    if matching_docs:
        durations = [
            int(((d.parsed or {}).get("render") or {}).get("duration_ms") or 0)
            for d in matching_docs
        ]
        if durations:
            avg_ms = int(sum(durations) / len(durations))

    # 3. Last failure / success timestamps.
    last_failed_at: str | None = None
    last_succeeded_at: str | None = None
    for e in events:
        is_bad = (e.meta or {}).get("quality_status") == "blocked" or \
                  (e.meta or {}).get("fallback_used")
        ts = e.at.isoformat() if e.at else None
        if is_bad and last_failed_at is None:
            last_failed_at = ts
        if not is_bad and last_succeeded_at is None:
            last_succeeded_at = ts

    # 4. Compose the operational score.
    score = (
        45 * success_rate                       # core: did it actually work
        + 35 * (avg_quality / 100)              # how good was the result
        - 20 * fallback_rate                    # penalise fallback drops
        - 15 * blocked_rate                     # penalise QA blocks
        + 35                                     # baseline (so a perfect template = 100)
    )
    score = max(0, min(100, int(round(score))))

    drivers: list[str] = []
    if n < 5:
        drivers.append(f"Limited history: only {n} render(s) in the lookback window.")
    if fallback_rate > 0.2:
        drivers.append(f"{int(fallback_rate * 100)}% of renders fell back to built-in HTML.")
    if blocked_rate > 0.2:
        drivers.append(f"{int(blocked_rate * 100)}% of renders were quality-blocked.")
    if avg_quality >= 85:
        drivers.append(f"Average render quality is high ({avg_quality:.0f}/100).")
    elif avg_quality < 60:
        drivers.append(f"Average render quality is low ({avg_quality:.0f}/100).")
    if success_rate >= 0.9:
        drivers.append(f"{int(success_rate * 100)}% successful renders.")

    return TemplateReliability(
        template_id=template_id, operational_score=score,
        sample_size=n, cold_start=False,
        render_success_rate=success_rate, fallback_rate=fallback_rate,
        avg_quality_score=avg_quality, blocked_approval_rate=blocked_rate,
        avg_render_ms=avg_ms,
        last_failed_at=last_failed_at, last_succeeded_at=last_succeeded_at,
        drivers=drivers,
    )


async def reliability_bonus_map(
    session: AsyncSession, *, company_id: str, template_ids: list[str],
) -> dict[str, tuple[int, int]]:
    """Batch helper for the matcher. Returns ``{template_id: (bonus, operational_score)}``.

    Computing reliability for every candidate during a match call is O(N) DB
    work; in practice the candidate set is small (verified templates of one
    kind) so this stays cheap. If the candidate list grows, swap this for a
    materialised view.
    """
    out: dict[str, tuple[int, int]] = {}
    for tid in template_ids:
        try:
            r = await compute_reliability(session, template_id=tid, company_id=company_id)
            out[tid] = (r.matcher_bonus(), r.operational_score)
        except Exception:  # noqa: BLE001 — reliability is advisory; never block matching
            out[tid] = (0, COLD_START_SCORE)
    return out
