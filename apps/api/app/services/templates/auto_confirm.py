"""Safe bulk auto-confirmation of template mappings.

Rules (deliberately conservative — accounting trust > coverage):

  AUTO-CONFIRM ONLY IF
    1. canonical key ∈ SAFE_FIELDS
    2. mapping confidence ≥ 0.90
    3. source_label is NOT already used by any other canonical key in this template
       (no conflict)
    4. mapping is not already confirmed
    5. canonical key ∉ RISKY_FIELDS (defence in depth)

  NEVER auto-confirm RISKY_FIELDS — these always require human review.

The auto-confirmation tags each mutation with metadata so it can be rolled back
deterministically. A successful auto-confirm pass may upgrade the template to
VERIFIED (all required fields confirmed) or PARTIALLY_VERIFIED (safe required
fields confirmed but risky/optional fields still pending).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.db.models import Template
from app.services.audit.logger import AuditLogger
from app.services.templates.service import REQUIRED_FOR_KIND
from app.services.templates.validator import validate as validate_template


SAFE_FIELDS:  set[str] = {
    "company_name", "client_name", "invoice_number",
    "invoice_date", "total", "currency",
}
RISKY_FIELDS: set[str] = {
    "vat", "vat_percent", "subtotal",
    "company_bin", "client_bin",
    "company_bank", "company_address", "client_address",
    "signature_block", "director_name", "accountant_name",
}
SAFE_MIN_CONFIDENCE = 0.90


@dataclass
class TemplateChange:
    template_id: str
    template_name: str
    kind: str
    confirmed: list[dict[str, Any]] = field(default_factory=list)
    skipped_low_confidence: int = 0
    skipped_risky: int = 0
    skipped_conflict: int = 0
    skipped_already_confirmed: int = 0
    new_status: str | None = None


@dataclass
class AutoConfirmReport:
    scanned: int = 0
    affected: int = 0
    auto_confirmed_total: int = 0
    by_field: Counter = field(default_factory=Counter)
    status_changes: Counter = field(default_factory=Counter)
    per_template: list[TemplateChange] = field(default_factory=list)
    skipped_low_confidence: int = 0
    skipped_risky: int = 0
    skipped_conflict: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned, "affected": self.affected,
            "auto_confirmed_total": self.auto_confirmed_total,
            "by_field": dict(self.by_field),
            "status_changes": dict(self.status_changes),
            "skipped": {
                "low_confidence": self.skipped_low_confidence,
                "risky":          self.skipped_risky,
                "conflict":       self.skipped_conflict,
            },
            "per_template": [
                {
                    "id": c.template_id, "name": c.template_name, "kind": c.kind,
                    "confirmed": c.confirmed,
                    "new_status": c.new_status,
                    "skipped_low_confidence": c.skipped_low_confidence,
                    "skipped_risky":          c.skipped_risky,
                    "skipped_conflict":       c.skipped_conflict,
                }
                for c in self.per_template if c.confirmed or c.new_status
            ][:60],
        }


async def auto_confirm_corpus(session, *, company_id: str, actor_id: str) -> AutoConfirmReport:
    """Run safe auto-confirm across every non-archived template for the company."""
    from sqlalchemy import select
    audit = AuditLogger()
    rows = list(await session.scalars(
        select(Template).where(
            Template.company_id == company_id,
            Template.status != "ARCHIVED",
        ),
    ))
    report = AutoConfirmReport(scanned=len(rows))

    for tpl in rows:
        change = _process_template(tpl)
        if change.confirmed:
            report.affected += 1
            report.auto_confirmed_total += len(change.confirmed)
            for c in change.confirmed:
                report.by_field[c["field"]] += 1
            await audit.record(
                session, company_id=company_id, actor_type="system", actor_id=actor_id,
                action="template.mapping_auto_confirmed", resource=tpl.id,
                meta={"count": len(change.confirmed),
                      "fields": [c["field"] for c in change.confirmed]},
            )
        report.skipped_low_confidence += change.skipped_low_confidence
        report.skipped_risky          += change.skipped_risky
        report.skipped_conflict       += change.skipped_conflict

        # Re-validate and upgrade status accordingly.
        old = tpl.status
        score, warnings, qa = validate_template(tpl)
        tpl.validation_score = score
        tpl.validation_warnings = warnings
        new_status = _derive_new_status(tpl, qa)
        if new_status != old:
            tpl.status = new_status
            change.new_status = new_status
            report.status_changes[f"{old}→{new_status}"] += 1
            await audit.record(
                session, company_id=company_id, actor_type="system", actor_id=actor_id,
                action="template.status_changed", resource=tpl.id,
                meta={"from": old, "to": new_status, "score": score,
                      "trigger": "auto_confirm"},
            )
        report.per_template.append(change)
    return report


def _process_template(tpl: Template) -> TemplateChange:
    change = TemplateChange(template_id=tpl.id, template_name=tpl.name, kind=tpl.kind)
    mappings: dict[str, dict[str, Any]] = dict(tpl.mappings or {})
    if not mappings:
        return change

    # Build source-label index to detect conflicts within the template.
    src_counts: Counter = Counter(
        ((m.get("source_label") or "").strip().lower())
        for m in mappings.values()
        if m.get("source_label")
    )

    for field_key, m in list(mappings.items()):
        if m.get("confirmed"):
            change.skipped_already_confirmed += 1
            continue
        # Hard guard: never touch RISKY_FIELDS.
        if field_key in RISKY_FIELDS:
            change.skipped_risky += 1
            continue
        if field_key not in SAFE_FIELDS:
            # Out of safe set — leave for human.
            continue
        conf = float(m.get("confidence") or 0)
        if conf < SAFE_MIN_CONFIDENCE:
            change.skipped_low_confidence += 1
            continue
        src = (m.get("source_label") or "").strip().lower()
        if not src:
            change.skipped_low_confidence += 1
            continue
        if src_counts[src] > 1:
            # Same source label maps to multiple canonical keys — conflict.
            change.skipped_conflict += 1
            continue
        # Safe to auto-confirm.
        m["confirmed"] = True
        m["auto_confirmed"] = True
        m["auto_confirmed_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        m["auto_confirmed_reason"] = (
            f"safe-field; confidence={conf:.2f}; unique source label"
        )
        mappings[field_key] = m
        change.confirmed.append({
            "field": field_key, "source_label": m.get("source_label"),
            "confidence": conf,
        })

    tpl.mappings = mappings
    return change


def _derive_new_status(tpl: Template, qa: str) -> str:
    """Map validator's QA status to operational template status with the new
    PARTIALLY_VERIFIED tier.

    Rules:
      * BROKEN     → FAILED   (unchanged behaviour)
      * VERIFIED   → VERIFIED
      * If every REQUIRED safe field is confirmed but some risky/optional
        remain unconfirmed → PARTIALLY_VERIFIED
      * else NEEDS_REVIEW → keep current status
    """
    if qa == "BROKEN":
        return "FAILED"
    if qa == "VERIFIED":
        return "VERIFIED"
    mappings = tpl.mappings or {}
    required = REQUIRED_FOR_KIND.get(tpl.kind, set())
    confirmed = {k for k, m in mappings.items() if m.get("confirmed")}
    required_safe = required & SAFE_FIELDS
    if required_safe and required_safe.issubset(confirmed):
        return "PARTIALLY_VERIFIED"
    return tpl.status if tpl.status not in ("UPLOADED", "ANALYZED") else "NEEDS_REVIEW"


async def rollback_auto_confirms(
    session, *, company_id: str, actor_id: str, template_id: str | None = None,
) -> dict[str, Any]:
    """Undo every mapping flagged `auto_confirmed=True`. Optional scope: a single template."""
    from sqlalchemy import select
    audit = AuditLogger()
    q = select(Template).where(
        Template.company_id == company_id, Template.status != "ARCHIVED",
    )
    if template_id:
        q = q.where(Template.id == template_id)
    rows = list(await session.scalars(q))
    rolled = 0
    affected = 0
    for tpl in rows:
        m = dict(tpl.mappings or {})
        touched = False
        for k, v in m.items():
            if v.get("auto_confirmed"):
                v["confirmed"] = False
                v.pop("auto_confirmed", None)
                v.pop("auto_confirmed_at", None)
                v.pop("auto_confirmed_reason", None)
                rolled += 1
                touched = True
        if touched:
            tpl.mappings = m
            affected += 1
            # Re-derive status downward when we lose confirmations.
            score, warnings, qa = validate_template(tpl)
            tpl.validation_score = score
            tpl.validation_warnings = warnings
            tpl.status = _derive_new_status(tpl, qa)
            await audit.record(
                session, company_id=company_id, actor_type="user", actor_id=actor_id,
                action="template.mapping_rollback", resource=tpl.id,
                meta={"unconfirmed": rolled},
            )
    return {"rolled_back": rolled, "templates_affected": affected}
