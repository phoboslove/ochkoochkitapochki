"""Pilot-operations analytics — admin-only operational metrics."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, require_admin
from app.db.models import Approval, AuditLog, Document, Invoice

router = APIRouter()


@router.get("/operational")
async def operational_metrics(
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=30)
    cid = user.company_id

    docs = list(await session.scalars(
        select(Document).where(Document.company_id == cid, Document.created_at >= cutoff),
    ))
    parsed = [d for d in docs if d.status == "PARSED"]
    failed = [d for d in docs if d.status == "FAILED"]
    confidences = [
        float((d.meta or {}).get("ocr_confidence", 1.0))
        for d in parsed if (d.meta or {}).get("ocr_confidence") is not None
    ]
    needs_review = sum(1 for d in parsed if (d.meta or {}).get("needs_review"))

    approvals = list(await session.scalars(
        select(Approval).where(Approval.company_id == cid, Approval.created_at >= cutoff),
    ))
    decided = [a for a in approvals if a.decided_at is not None]
    latencies = [(a.decided_at - a.created_at).total_seconds() for a in decided]

    invoices = list(await session.scalars(
        select(Invoice).where(Invoice.company_id == cid, Invoice.created_at >= cutoff),
    ))
    sent = [i for i in invoices if i.status in {"SENT", "PAID"}]

    rows = await session.execute(
        select(AuditLog.action, func.count(AuditLog.id)).where(
            AuditLog.company_id == cid, AuditLog.at >= cutoff,
        ).group_by(AuditLog.action),
    )
    by_action = {a: n for a, n in rows.all()}

    workflow_runs = (by_action.get("workflow.run_started", 0) +
                     by_action.get("invoice.create_draft", 0))
    workflow_failed = sum(v for k, v in by_action.items() if k.endswith(".failed") or k.endswith(".send_failed"))

    return {
        "window_days": 30,
        "ocr": {
            "documents_total":    len(docs),
            "documents_parsed":   len(parsed),
            "documents_failed":   len(failed),
            "failure_rate":       round(len(failed) / max(len(docs), 1), 3),
            "avg_confidence":     round(sum(confidences) / max(len(confidences), 1), 3) if confidences else None,
            "low_confidence_pct": round(sum(1 for c in confidences if c < 0.65) / max(len(confidences), 1), 3) if confidences else None,
            "needs_review":       needs_review,
        },
        "workflows": {
            "runs":         workflow_runs,
            "failures":     workflow_failed,
            "success_rate": round(1 - (workflow_failed / max(workflow_runs, 1)), 3) if workflow_runs else None,
        },
        "approvals": {
            "requested": len(approvals),
            "decided":   len(decided),
            "avg_latency_seconds": round(sum(latencies) / max(len(latencies), 1)) if latencies else None,
            "median_latency_seconds": (sorted(latencies)[len(latencies)//2] if latencies else None),
        },
        "ai_tools": {
            "invoked": by_action.get("ai.tool_invoked", 0),
            "denied":  by_action.get("ai.tool_denied", 0),
            "high_value_blocked": sum(v for k, v in by_action.items() if k == "ai.tool_invoked" and False),  # placeholder
        },
        "invoices": {"created": len(invoices), "sent": len(sent)},
        "recovery": {
            "unique_failures": len({a for a in by_action if a.endswith(".failed")}),
            "total_failures":  workflow_failed,
        },
        "anomalies": {
            "duplicate_clients": by_action.get("client.possible_duplicate", 0),
        },
    }


@router.get("/ocr-benchmark")
async def ocr_benchmark(
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """OCR quality cohort: extracted vs human-corrected.

    A document is considered manually corrected when an audit entry
    `document.fields_updated` exists for it. Useful for tuning OCR providers.
    """
    cid = user.company_id
    docs = list(await session.scalars(
        select(Document).where(Document.company_id == cid),
    ))
    corrections = list(await session.scalars(
        select(AuditLog).where(
            AuditLog.company_id == cid,
            AuditLog.action == "document.fields_updated",
        ).order_by(desc(AuditLog.at)),
    ))
    corrected_ids = {c.resource for c in corrections if c.resource}

    by_mime: dict[str, dict] = {}
    for d in docs:
        bucket = by_mime.setdefault(d.mime, {"count": 0, "corrected": 0, "low_conf": 0, "failed": 0,
                                              "confidences": []})
        bucket["count"] += 1
        if d.id in corrected_ids: bucket["corrected"] += 1
        conf = (d.meta or {}).get("ocr_confidence")
        if conf is not None:
            bucket["confidences"].append(float(conf))
            if conf < 0.65: bucket["low_conf"] += 1
        if d.status == "FAILED": bucket["failed"] += 1

    cohorts: list[dict] = []
    for mime, b in sorted(by_mime.items(), key=lambda kv: -kv[1]["count"]):
        c = b["confidences"]
        cohorts.append({
            "mime": mime, "count": b["count"], "corrected": b["corrected"],
            "correction_rate": round(b["corrected"] / max(b["count"], 1), 3),
            "low_confidence":  b["low_conf"], "failed": b["failed"],
            "avg_confidence":  round(sum(c) / max(len(c), 1), 3) if c else None,
        })
    return {
        "cohorts": cohorts,
        "manual_corrections": len(corrections),
        "documents_total":    len(docs),
        "correction_rate":    round(len(corrected_ids) / max(len(docs), 1), 3),
    }
