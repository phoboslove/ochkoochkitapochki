"""Template validation — derives QA score from declarative checks.

Each check returns a list of warnings. Score = 100 − Σ severity weights.
Pure function; no DB writes. Caller persists results back to Template.
"""
from __future__ import annotations

from typing import Any, Literal

from app.db.models import Template
from app.services.templates.placeholders import CANONICAL
from app.services.templates.service import REQUIRED_FOR_KIND


Severity = Literal["info", "warn", "high", "critical"]
WEIGHT: dict[Severity, int] = {"info": 2, "warn": 6, "high": 14, "critical": 30}


def validate(tpl: Template) -> tuple[int, list[dict[str, Any]], str]:
    """Returns (score 0..100, warnings, qa_status).

    qa_status ∈ {VERIFIED, PARTIAL, NEEDS_REVIEW, BROKEN} — drives the badge UI.
    """
    warnings: list[dict[str, Any]] = []
    mappings = tpl.mappings or {}
    confirmed = {k for k, m in mappings.items() if m.get("confirmed")}
    required = REQUIRED_FOR_KIND.get(tpl.kind, set())

    # ── Critical: legacy or hard-broken file ──────────────────────────────
    if tpl.format in ("doc", "xls"):
        warnings.append({
            "code": "legacy_format", "severity": "critical",
            "message": f"Legacy {tpl.format.upper()} (Office 97-2003) cannot be parsed by Python.",
            "fix": f"Convert to {'DOCX' if tpl.format == 'doc' else 'XLSX'} (Recovery → Convert).",
        })

    if tpl.last_error:
        warnings.append({
            "code": "render_failed", "severity": "high",
            "message": f"Last render failed: {tpl.last_error[:160]}",
            "fix": "Re-confirm mappings and run preview again.",
        })

    # ── Required mappings missing ─────────────────────────────────────────
    missing_required = [k for k in required if k not in confirmed]
    for k in missing_required:
        warnings.append({
            "code": "missing_required", "severity": "high",
            "message": f"Required mapping {k!r} for {tpl.kind} is not confirmed.",
            "fix": f"Open mapping panel and confirm {CANONICAL[k].label}.",
        })

    # ── Unconfirmed suggestions ───────────────────────────────────────────
    unconfirmed = [k for k, m in mappings.items() if not m.get("confirmed")]
    if unconfirmed:
        warnings.append({
            "code": "unconfirmed", "severity": "warn",
            "message": f"{len(unconfirmed)} mapping(s) suggested but unconfirmed.",
            "fix": "Review the right-side mapping panel and confirm or remap.",
        })

    # ── Duplicate semantic field (two canonical keys point to same source) ─
    seen: dict[str, list[str]] = {}
    for k, m in mappings.items():
        if not m.get("confirmed"): continue
        seen.setdefault((m.get("source_label") or "").strip().lower(), []).append(k)
    dups = {src: keys for src, keys in seen.items() if src and len(keys) > 1}
    for src, keys in dups.items():
        warnings.append({
            "code": "duplicate_source", "severity": "warn",
            "message": f"Source label {src!r} mapped to multiple canonical fields: {', '.join(keys)}.",
            "fix": "Remap one of the fields to a more specific source label.",
        })

    # ── Tables present but {{items}} unmapped ─────────────────────────────
    has_tables = bool(tpl.detected_tables) and any(
        t.get("is_repeating") for t in (tpl.detected_tables or [])
    )
    if has_tables and "items" not in confirmed:
        warnings.append({
            "code": "items_unmapped", "severity": "high",
            "message": "Repeating table detected but {{items}} is not confirmed.",
            "fix": "Confirm Line items mapping so the renderer can expand rows.",
        })

    # ── Totals / VAT sanity for invoice-like templates ────────────────────
    if tpl.kind in ("invoice", "nakladnaya"):
        if "total" not in confirmed:
            warnings.append({
                "code": "no_total", "severity": "high",
                "message": "No total amount mapped on an invoice-like template.",
                "fix": "Confirm a mapping for {{total}} (e.g. \"Итого к оплате\").",
            })
        if "vat" not in confirmed:
            warnings.append({
                "code": "no_vat", "severity": "info",
                "message": "No VAT field mapped. Fine if your company is non-VAT.",
                "fix": "Map {{vat}} only if your company applies НДС.",
            })

    # ── Existing {{placeholders}} not in CANONICAL ────────────────────────
    raw_placeholders = (tpl.detected_fields or {}).get("placeholders", []) or []
    foreign = [p for p in raw_placeholders if p not in CANONICAL and "." not in p]
    if foreign:
        warnings.append({
            "code": "foreign_placeholders", "severity": "warn",
            "message": f"Template references {len(foreign)} non-standard placeholder(s): {', '.join(foreign[:4])}…",
            "fix": "Either map them via the panel or replace them with canonical names.",
        })

    # ── Very low avg suggestion confidence ────────────────────────────────
    if mappings and (tpl.confidence or 0) < 0.45:
        warnings.append({
            "code": "low_confidence", "severity": "warn",
            "message": f"Average suggestion confidence is only {round((tpl.confidence or 0) * 100)}%.",
            "fix": "Verify the source-label dropdowns — auto-suggestions are weak for this doc.",
        })

    # ── Score + status ────────────────────────────────────────────────────
    deduction = sum(WEIGHT[w["severity"]] for w in warnings)
    score = max(0, 100 - deduction)

    if any(w["severity"] == "critical" for w in warnings):
        qa = "BROKEN"
    elif missing_required or any(w["severity"] == "high" for w in warnings):
        qa = "NEEDS_REVIEW"
    elif warnings:
        qa = "PARTIAL"
    else:
        qa = "VERIFIED"
    return score, warnings, qa
