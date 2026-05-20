"""Full-corpus audit — combines integrity / mapping-quality / render-check /
recovery-audit checks into one report. Pure analyze + persist; no destructive ops.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Template
from app.services.audit.logger import AuditLogger
from app.services.storage import get_storage
from app.services.templates.placeholders import CANONICAL
from app.services.templates.renderer import (
    build_context_from_template, build_demo_context, render_template,
)
from app.services.templates.service import REQUIRED_FOR_KIND
from app.services.templates.validator import validate as validate_template


async def audit_corpus(
    session: AsyncSession, *, company_id: str, render_check: bool = True, render_sample: int = 12,
) -> dict[str, Any]:
    rows = list(await session.scalars(
        select(Template).where(Template.company_id == company_id).order_by(desc(Template.created_at)),
    ))
    storage = get_storage()
    audit = AuditLogger()

    # ── 1) Corpus summary ─────────────────────────────────────────────────
    by_status = Counter(t.status for t in rows)
    by_kind = Counter(t.kind for t in rows)
    by_industry = Counter(t.industry or "general" for t in rows)
    by_format = Counter(t.format for t in rows)
    by_language = Counter(t.language or "—" for t in rows)
    hashes = Counter(t.file_hash for t in rows if t.file_hash)
    duplicate_hashes = {h: n for h, n in hashes.items() if n > 1}

    # ── 2) Ingestion integrity ────────────────────────────────────────────
    integrity = {
        "storage_missing": [], "empty_content": [], "malformed_mappings": [],
        "broken_lineage": [], "no_paragraphs": [],
    }
    for t in rows:
        if t.format != "html" and t.body:
            try: storage.get(t.body)
            except Exception:
                integrity["storage_missing"].append(_brief(t))
        paragraphs = (t.detected_fields or {}).get("paragraphs", []) or []
        if not paragraphs and t.format not in ("doc", "xls", "html"):
            integrity["no_paragraphs"].append(_brief(t))
        m = t.mappings
        if m is not None and not isinstance(m, dict):
            integrity["malformed_mappings"].append(_brief(t))
        elif m:
            for k, v in m.items():
                if not isinstance(v, dict) or "confidence" not in v:
                    integrity["malformed_mappings"].append(_brief(t)); break
        if t.converted_from_id:
            parent = await session.get(Template, t.converted_from_id)
            if not parent or parent.company_id != company_id:
                integrity["broken_lineage"].append(_brief(t))

    # ── 3) Mapping quality audit ──────────────────────────────────────────
    mapping_quality: dict[str, list] = {
        "low_confidence": [], "missing_required": [], "duplicate_sources": [],
        "suspicious_total_vs_subtotal": [],
    }
    confirmed_global: Counter = Counter()
    for t in rows:
        m = t.mappings or {}
        confirmed = {k for k, v in m.items() if v.get("confirmed")}
        required = REQUIRED_FOR_KIND.get(t.kind, set())
        missing = required - confirmed
        if missing:
            mapping_quality["missing_required"].append({**_brief(t), "missing": sorted(missing)})
        for k, v in m.items():
            confirmed_global[k] += 1 if v.get("confirmed") else 0
            if (v.get("confidence") or 0) < 0.5 and not v.get("confirmed"):
                mapping_quality["low_confidence"].append(
                    {**_brief(t), "field": k, "label": v.get("source_label", ""),
                     "confidence": v.get("confidence")},
                )
        seen: dict[str, list[str]] = defaultdict(list)
        for k, v in m.items():
            if v.get("confirmed"):
                seen[(v.get("source_label") or "").strip().lower()].append(k)
        for src, keys in seen.items():
            if src and len(keys) > 1:
                mapping_quality["duplicate_sources"].append(
                    {**_brief(t), "source": src, "fields": keys},
                )
        # Suspicious: "total" mapped to something containing "без ндс"
        for canonical, suspect in (("total", "без ндс"), ("subtotal", "итого к оплате")):
            v = m.get(canonical)
            if v and suspect in (v.get("source_label") or "").lower():
                mapping_quality["suspicious_total_vs_subtotal"].append(
                    {**_brief(t), "field": canonical, "label": v.get("source_label")},
                )

    # ── 4) Render verification (sample) ───────────────────────────────────
    render_report = {"attempted": 0, "ok": 0, "failed": []}
    failure_patterns: Counter = Counter()
    if render_check:
        candidates = [t for t in rows if t.status not in ("ARCHIVED",) and t.format in ("docx","xlsx","html")]
        # Stratified sample — one of each kind/industry first, then by recency.
        seen_axes: set[tuple] = set()
        sample: list[Template] = []
        for t in candidates:
            axis = (t.kind, t.format)
            if axis not in seen_axes:
                seen_axes.add(axis); sample.append(t)
        for t in candidates:
            if t in sample: continue
            if len(sample) >= render_sample: break
            sample.append(t)
        for t in sample[:render_sample]:
            render_report["attempted"] += 1
            try:
                if t.format == "html":
                    body_bytes = (t.body or "").encode("utf-8")
                else:
                    body_bytes = storage.get(t.body)
                ctx = build_context_from_template(t.mappings or {}, build_demo_context())
                rendered, _mime, _ext = render_template(content=body_bytes, format=t.format, context=ctx)
                if not rendered or len(rendered) < 100:
                    raise RuntimeError("renderer produced suspiciously small output")
                render_report["ok"] += 1
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).splitlines()[-1][:200]
                render_report["failed"].append({**_brief(t), "error": msg})
                pat = _classify_failure(msg)
                failure_patterns[pat] += 1
    render_report["failure_patterns"] = dict(failure_patterns)

    # ── 5) Recovery / audit visibility ────────────────────────────────────
    cutoff = datetime.utcnow() - timedelta(days=14)
    fail_rows = await session.execute(
        select(AuditLog.action, func.count(AuditLog.id)).where(
            AuditLog.company_id == company_id, AuditLog.at >= cutoff,
            AuditLog.action.in_((
                "template.conversion_failed", "template.render_failed",
                "template.uploaded", "template.converted", "template.validated",
                "template.bulk_reclassified",
            )),
        ).group_by(AuditLog.action),
    )
    recovery = {action: n for action, n in fail_rows.all()}

    # ── 6) Aggregate scores ───────────────────────────────────────────────
    total = len(rows)
    operational = sum(1 for t in rows if t.status in ("VERIFIED","MAPPED","ANALYZED"))
    verified = by_status.get("VERIFIED", 0)
    broken = by_status.get("FAILED", 0) + by_status.get("ARCHIVED", 0)
    # Production-readiness score: weight verified, render success, integrity.
    integrity_penalty = sum(len(v) for v in integrity.values()) * 2
    mapping_penalty = sum(len(v) for v in mapping_quality.values())
    render_rate = (render_report["ok"] / render_report["attempted"]) if render_report["attempted"] else 1.0
    base = 100
    score = max(0, base
                 - int(integrity_penalty)
                 - int(mapping_penalty * 0.5)
                 - int((1 - render_rate) * 40)
                 - int((broken / max(total,1)) * 30))

    # Top blockers + recommendations.
    blockers: list[str] = []
    recommendations: list[str] = []
    if integrity["storage_missing"]:
        blockers.append(f"{len(integrity['storage_missing'])} template(s) reference missing files in storage")
        recommendations.append("Reupload affected templates or restore the storage backup.")
    if mapping_quality["missing_required"]:
        blockers.append(f"{len(mapping_quality['missing_required'])} template(s) miss required mappings")
        recommendations.append("Open each in /settings/templates and confirm required fields.")
    if render_report["failed"]:
        blockers.append(f"{len(render_report['failed'])} sample render failure(s)")
        recommendations.append("Investigate render errors below; most patterns: " +
                                 ", ".join(failure_patterns.keys()) if failure_patterns else "")
    if broken / max(total, 1) > 0.3:
        blockers.append(f"{broken} template(s) marked FAILED or ARCHIVED ({round(broken/total*100)}%)")
        recommendations.append("Run /templates/convert-legacy-all once LibreOffice is installed; "
                                "re-run /templates/reclassify-all afterwards.")

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "corpus_summary": {
            "total": total, "verified": verified, "operational": operational,
            "broken": broken, "duplicates": len(duplicate_hashes),
            "by_status":   dict(by_status), "by_kind":     dict(by_kind),
            "by_industry": dict(by_industry), "by_format":   dict(by_format),
            "by_language": dict(by_language),
        },
        "integrity":       {k: v[:30] for k, v in integrity.items()},
        "integrity_counts":{k: len(v) for k, v in integrity.items()},
        "mapping_quality": {k: v[:30] for k, v in mapping_quality.items()},
        "mapping_counts":  {k: len(v) for k, v in mapping_quality.items()},
        "render_check":    render_report,
        "recovery":        recovery,
        "production_readiness": {
            "score": score,
            "verified_pct": round((verified / max(total, 1)) * 100, 1),
            "render_success_rate": round(render_rate * 100, 1),
            "blockers": blockers,
            "recommendations": recommendations,
        },
    }
    await audit.record(
        session, company_id=company_id, actor_type="user", actor_id="audit",
        action="template.corpus_audit",
        meta={"score": score, "verified": verified, "broken": broken,
              "render_ok": render_report["ok"], "render_attempted": render_report["attempted"]},
    )
    return report


def _brief(t: Template) -> dict:
    return {"id": t.id, "name": t.name, "kind": t.kind, "format": t.format,
            "filename": t.original_filename, "status": t.status}


def _classify_failure(msg: str) -> str:
    m = msg.lower()
    if "docxtpl" in m or "jinja"  in m: return "template_syntax"
    if "openpyxl" in m or "cell"  in m: return "xlsx_structure"
    if "no such file" in m or "missing" in m: return "missing_file"
    if "permission" in m: return "permission"
    if "encoding" in m: return "encoding"
    return "other"
