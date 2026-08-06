"""GenerationPipeline — single orchestration entrypoint for AI-generated docs.

Flow (Phase 1 + 2 + 5):
  intent (RU/EN NL parse, with optional explicit overrides)
    → match best VERIFIED template (kind-filtered, semantic-aware)
    → build canonical context (BusinessContext + intent + overrides)
    → render DOCX/XLSX via template, OR HTML fallback for kinds w/o template
    → PDF export (best-effort) for preview
    → persist both originals + PDF to storage
    → create Document row (type=KIND, status=GENERATED)
    → audit + bump template usage
    → request approval (non-blocking — document is downloadable immediately)

Returns a `GenerationResult` carrying URLs + metadata. The caller (AI tool /
API endpoint) shapes it into the UI card.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Any

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Approval, Document, Template
from app.services.audit.logger import AuditLogger
from app.services.context.service import load_context
from app.services.documents.generation.adapter import adapt_template
from app.services.documents.generation.context_builder import build_canonical_context
from app.services.documents.generation.diagnostics import (
    STAGE_INTENT, STAGE_MATCH, STAGE_PDF_EXPORT, STAGE_RENDER, STAGE_STORAGE,
    DiagnosticsCollector,
)
from app.services.documents.generation.intent import IntentSpec, parse_intent
from app.services.documents.generation.quality import (
    QUALITY_BLOCK_THRESHOLD, QualityReport, check_render_quality,
)
from app.services.storage import get_storage
from app.services.templates.matcher import bump_success, match_best
from app.services.templates.renderer import build_context_from_template, render_template

SUPPORTED_KINDS = {"invoice", "act", "nakladnaya", "contract", "trust_letter", "arbitrary_template"}

_KIND_TO_DOCTYPE = {
    "invoice": "INVOICE", "act": "ACT", "nakladnaya": "NAKLADNAYA",
    "contract": "CONTRACT", "trust_letter": "TRUST_LETTER",
    "arbitrary_template": "OTHER",
}

_KIND_TO_NUM_PREFIX = {
    "invoice": "INV", "act": "ACT", "nakladnaya": "NKL",
    "contract": "DOG", "trust_letter": "DOV", "arbitrary_template": "DOC",
}


@dataclass
class GenerationResult:
    document_id: str
    kind: str
    document_number: str
    template_id: str | None
    template_name: str | None
    template_format: str | None
    match_reason: str
    match_score: int
    confidence: float
    docx_url: str | None
    pdf_url: str | None
    primary_url: str
    approval_id: str | None
    approval_status: str | None
    render_duration_ms: int
    template_verified: bool = False
    template_operational_score: int | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None
    fallback_engine: str | None = None
    adaptation_applied: bool = False
    adaptation_anchors_injected: int = 0
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    canonical_context: dict[str, Any] = field(default_factory=dict)


class GenerationPipeline:
    def __init__(self) -> None:
        self.audit = AuditLogger()
        self.storage = get_storage()

    # ── Public ────────────────────────────────────────────────────────────

    async def generate(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        actor_id: str,
        actor_type: str = "ai",
        kind: str,
        prompt: str | None = None,
        overrides: dict[str, Any] | None = None,
        conversation_id: str | None = None,
        require_approval: bool = True,
    ) -> GenerationResult:
        """Produce a real populated business document.

        ``prompt`` is the user's NL request (e.g. "Создай акт для TOO Sigma на 450000 KZT").
        ``overrides`` are typed fields the AI extracted itself (client_name,
        total, items, currency, vat_percent, notes, etc.) and take precedence.
        """
        if kind not in SUPPORTED_KINDS:
            raise ValueError(f"unsupported kind: {kind}")

        t0 = perf_counter()
        diag = DiagnosticsCollector()
        fallback_used = False
        fallback_reason: str | None = None
        fallback_engine: str | None = None
        adaptation_count = 0
        intent = await self._build_intent(kind=kind, prompt=prompt, overrides=overrides)
        diag.info(STAGE_INTENT, "intent_parsed",
                   f"Parsed intent: kind={intent.kind} client={intent.client_name!r} "
                   f"total={intent.total} currency={intent.currency} "
                   f"confidence={intent.confidence:.2f}.",
                   extra={"keywords": intent.kind_keywords_matched})

        # 1) Pick template (VERIFIED, kind-filtered, semantic-aware).
        match = await match_best(
            session, company_id=company_id, kind=kind,
            query=intent.raw_text or (intent.client_name or "") + " " + (intent.item_description or ""),
        )
        template = match.template
        business = await load_context(session, company_id)
        if template:
            diag.info(STAGE_MATCH, "template_matched",
                       f"Matched template '{template.name}' (score {match.score}).",
                       template_id=template.id,
                       extra={"reason": match.reason, "ambiguous": match.ambiguous})
        else:
            diag.warn(STAGE_MATCH, "no_verified_template",
                       f"No VERIFIED template for kind={kind}. Falling back to built-in HTML.",
                       suggested_fix=(
                           "Upload a DOCX/XLSX template of the right kind and run the "
                           "mapping wizard until status = VERIFIED."
                       ))

        # 2) Build canonical context.
        document_number = await self._next_number(session, company_id, kind=kind)
        canonical = build_canonical_context(
            business=business, intent=intent,
            document_number=document_number, overrides=overrides,
        )

        # 3) Render — template path or HTML fallback. Adaptation runs FIRST for
        #    legacy templates so {{anchors}} exist before render_template walks.
        render_warnings: list[str] = []
        if template:
            try:
                doc_bytes, mime, ext, adaptation_count = await self._render_with_template(
                    template, canonical, diag,
                )
            except Exception as exc:  # noqa: BLE001
                # Render of the matched template failed — degrade to HTML fallback
                # but expose exactly which stage broke.
                diag.error(STAGE_RENDER, "template_render_failed",
                            f"Render of template '{template.name}' raised: {exc!s}",
                            template_id=template.id, exception=str(exc)[:200],
                            render_engine=("docxtpl" if template.format == "docx"
                                            else "openpyxl" if template.format == "xlsx" else None),
                            suggested_fix="Open the template, fix the broken section "
                                          "(usually a placeholder syntax error) and re-verify.")
                render_warnings.append(f"template_render_failed: {str(exc)[:160]}")
                fallback_used = True
                fallback_reason = f"template_render_failed: {str(exc)[:160]}"
                fallback_engine = "html_fallback"
                doc_bytes, mime, ext = self._render_html_fallback(kind, canonical)
        else:
            doc_bytes, mime, ext = self._render_html_fallback(kind, canonical)
            render_warnings.append(
                f"no VERIFIED template for kind={kind} — used built-in HTML fallback"
            )
            fallback_used = True
            fallback_reason = f"no_verified_template_for_{kind}"
            fallback_engine = "html_fallback"

        # 4) Storage — original.
        doc_id = f"gen_{uuid.uuid4().hex[:10]}"
        base_key = f"{company_id}/generated/{doc_id}/{document_number}"
        orig_key = f"{base_key}.{ext}"
        self.storage.put(orig_key, doc_bytes, content_type=mime)
        orig_url = self.storage.presign_get(orig_key, expires_in=3600)

        # 5) PDF — best-effort. Prefer real DOCX→PDF when possible, otherwise
        #    convert the HTML render with the in-process engine.
        pdf_url: str | None = None
        pdf_key: str | None = None
        pdf_bytes: bytes | None = None
        try:
            pdf_bytes, pdf_meta = await self._to_pdf(doc_bytes=doc_bytes, mime=mime, ext=ext)
            if pdf_bytes:
                pdf_key = f"{base_key}.pdf"
                self.storage.put(pdf_key, pdf_bytes, content_type="application/pdf")
                pdf_url = self.storage.presign_get(pdf_key, expires_in=3600)
                diag.info(STAGE_PDF_EXPORT, "pdf_exported",
                           f"PDF rendered via {pdf_meta.get('engine')} "
                           f"({pdf_meta.get('duration_ms','?')}ms, "
                           f"{pdf_meta.get('bytes', len(pdf_bytes))} bytes).",
                           render_engine=pdf_meta.get("engine"))
            else:
                reason = (pdf_meta or {}).get("reason") or "unknown reason"
                diag.warn(STAGE_PDF_EXPORT, "pdf_export_skipped",
                           f"PDF export skipped: {reason}.",
                           render_engine=(pdf_meta or {}).get("engine"),
                           suggested_fix=(
                               "Install LibreOffice for DOCX→PDF, or install WeasyPrint "
                               "system libraries for high-fidelity HTML→PDF."
                           ))
        except Exception as exc:  # noqa: BLE001
            render_warnings.append(f"pdf_export_failed: {str(exc)[:160]}")
            diag.error(STAGE_PDF_EXPORT, "pdf_export_failed",
                        f"PDF engine raised: {exc!s}",
                        exception=str(exc)[:200],
                        suggested_fix="Check PDF engine health at /health/diagnostics.")

        # 5b1) Pull operational reliability for the chosen template so the
        # tool/UI can display a trustworthy badge ("Reliability 92/100").
        template_op_score: int | None = None
        if template:
            try:
                from app.services.templates.reliability import compute_reliability
                rel = await compute_reliability(
                    session, template_id=template.id, company_id=company_id,
                )
                template_op_score = rel.operational_score
            except Exception:  # noqa: BLE001 — reliability is advisory
                template_op_score = None

        # 5b2) Real QA on the rendered artifacts. Drives the approval gate (Phase 6).
        quality = check_render_quality(
            canonical=canonical,
            rendered_bytes=doc_bytes, rendered_ext=ext,
            pdf_bytes=pdf_bytes,
            template_format=(template.format if template else None),
            pipeline_warnings=render_warnings,
        )

        # 6) Persist Document row.
        document = Document(
            id=doc_id, company_id=company_id,
            type=_KIND_TO_DOCTYPE.get(kind, "OTHER"),
            title=f"{_human_kind(kind)} {document_number}"
                  + (f" — {intent.client_name}" if intent.client_name else ""),
            storage_key=pdf_key or orig_key,
            mime="application/pdf" if pdf_key else mime,
            size=len(doc_bytes),
            checksum=None,
            status="GENERATED",
            parsed={
                "generated_by": "ai",
                "kind": kind,
                "document_number": document_number,
                "intent": {
                    "client_name": intent.client_name,
                    "total": intent.total,
                    "currency": intent.currency,
                    "kind_keywords": intent.kind_keywords_matched,
                    "confidence": round(intent.confidence, 2),
                },
                "template": ({"id": template.id, "name": template.name,
                               "format": template.format, "score": match.score,
                               "reason": match.reason, "status": template.status,
                               "verified": template.status == "VERIFIED",
                               "operational_score": template_op_score} if template else None),
                "conversation_id": conversation_id,
                "source_prompt": (prompt or "")[:1000],
                "render": {
                    "duration_ms": int((perf_counter() - t0) * 1000),
                    "format": ext, "mime": mime,
                    "docx_url": orig_url, "pdf_url": pdf_url,
                },
                "quality": quality.as_dict(),
                "diagnostics": diag.as_payload(),
                "adaptation": {
                    "applied": adaptation_count > 0,
                    "anchors_injected": adaptation_count,
                },
                "fallback": {
                    "used": fallback_used,
                    "reason": fallback_reason,
                    "engine": fallback_engine,
                },
            },
            meta={"warnings": render_warnings, "quality_status": quality.status,
                   "quality_score": quality.score,
                   "fallback_used": fallback_used,
                   "adaptation_anchors": adaptation_count},
            created_by=actor_id,
        )
        session.add(document)
        await session.flush()

        # 7) Bump template usage + audit.
        if template:
            template.last_render_at = datetime.utcnow()
            try:
                bump_success(template)
            except Exception:  # noqa: BLE001
                pass

        await self.audit.record(
            session, company_id=company_id,
            actor_type=actor_type, actor_id=actor_id,
            action="document.generated", resource=document.id,
            meta={
                "kind": kind, "number": document_number,
                "template_id": template.id if template else None,
                "match_score": match.score,
                "has_pdf": bool(pdf_url),
                "warnings": render_warnings,
                "quality_score": quality.score,
                "quality_status": quality.status,
            },
        )

        # 8) Approval — parallel, NON-blocking on download but quality-gated on
        #    *sending*. Status is BLOCKED when QA is below threshold; the doc
        #    stays previewable but won't dispatch until an operator clears it.
        approval_id: str | None = None
        approval_status: str | None = None
        if require_approval:
            approval_id, approval_status = await self._request_approval(
                session, company_id=company_id, document=document,
                actor_id=actor_id, intent=intent, document_number=document_number,
                quality=quality,
            )

        duration_ms = int((perf_counter() - t0) * 1000)
        return GenerationResult(
            document_id=document.id,
            kind=kind,
            document_number=document_number,
            template_id=template.id if template else None,
            template_name=template.name if template else None,
            template_format=template.format if template else "html",
            match_reason=match.reason,
            match_score=match.score,
            confidence=round(intent.confidence, 2),
            docx_url=orig_url,
            pdf_url=pdf_url,
            primary_url=pdf_url or orig_url,
            approval_id=approval_id,
            approval_status=approval_status,
            render_duration_ms=duration_ms,
            template_verified=bool(template and template.status == "VERIFIED"),
            template_operational_score=template_op_score,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            fallback_engine=fallback_engine,
            adaptation_applied=adaptation_count > 0,
            adaptation_anchors_injected=adaptation_count,
            diagnostics=diag.as_payload(),
            quality=quality.as_dict(),
            warnings=render_warnings,
            canonical_context={
                k: v for k, v in canonical.items()
                if not isinstance(v, (list, dict)) and v not in ("", None)
            },
        )

    # ── Internals ─────────────────────────────────────────────────────────

    async def _build_intent(
        self, *, kind: str, prompt: str | None, overrides: dict[str, Any] | None,
    ) -> IntentSpec:
        """Single canonical intent for the whole pipeline.

        Priority for ``parsed_items`` + ``total``:
          1. deterministic prompt parser (multi-line ``name — amount``)
          2. explicit ``overrides['items']`` (caller already merged in tool
             layer — propose/generate enforce parser-wins themselves;
             callers like ``_confirm_pending_proposal`` pass the snapshot
             that propose already validated)
          3. scalar ``overrides['total']`` fallback for single-item docs.

        Same rule as in registry._merge_items_into_intent so the two paths
        can NEVER diverge — this is the "data pipeline consistency" guarantee.
        """
        intent = await parse_intent(prompt or "")
        intent.kind = kind
        o = overrides or {}
        if o.get("client_name"):                intent.client_name = o["client_name"]
        if o.get("currency"):                   intent.currency = o["currency"]
        if o.get("vat_percent") is not None:    intent.vat_percent = float(o["vat_percent"])

        if intent.parsed_items:
            # Parser found multi-line items — they are the truth. Recompute
            # total from them and discard scalar overrides that would have
            # collapsed the table.
            intent.total = sum(float(it.get("total") or 0) for it in intent.parsed_items)
        elif o.get("items"):
            intent.parsed_items = list(o["items"])
            intent.total = sum(float(it.get("total") or 0) for it in intent.parsed_items)
        else:
            if o.get("total") is not None:        intent.total = float(o["total"])
            if o.get("item_description"):         intent.item_description = o["item_description"]
            if o.get("qty") is not None:          intent.qty = float(o["qty"])
        return intent

    async def _render_with_template(
        self, template: Template, canonical: dict[str, Any], diag: DiagnosticsCollector,
    ) -> tuple[bytes, str, str, int]:
        """Pull the template binary, transiently adapt legacy KZ layouts, render.

        Returns (bytes, mime, ext, adaptation_anchor_count).
        """
        if template.format in {"docx", "xlsx", "pdf", "doc", "xls"}:
            try:
                tpl_bytes = self.storage.get(template.body)
            except FileNotFoundError as exc:
                raise RuntimeError(f"template binary missing at {template.body}") from exc
        else:
            tpl_bytes = (template.body or "").encode("utf-8")

        # Phase 1 — Legacy adaptation. Transient: NEVER persisted back to storage.
        adapted_bytes, adapter_diag = await adapt_template(
            content=tpl_bytes, format=template.format,
            existing_mappings=template.mappings or {},
        )
        # Tag adapter diagnostics with the template id so the operator can pin
        # the issue to a specific template in the UI.
        for entry in adapter_diag.entries:
            entry.template_id = template.id
        diag.extend(adapter_diag.entries)
        anchors_injected = len(adapter_diag.filter(severity="info"))

        # Apply user-confirmed source-label aliases so DOCX placeholders that
        # use original RU/KZ labels (e.g. {{Поставщик}}) still resolve.
        ctx = build_context_from_template(template.mappings or {}, canonical)
        body, mime, ext = render_template(
            content=adapted_bytes, format=template.format, context=ctx,
        )
        return body, mime, ext, anchors_injected

    def _render_html_fallback(
        self, kind: str, canonical: dict[str, Any],
    ) -> tuple[bytes, str, str]:
        """Built-in HTML used when no VERIFIED template exists for this kind."""
        from app.services.documents.generation.html_fallback import render_fallback_html
        html = render_fallback_html(kind=kind, context=canonical)
        return html.encode("utf-8"), "text/html", "html"

    async def _to_pdf(
        self, *, doc_bytes: bytes, mime: str, ext: str,
    ) -> tuple[bytes | None, dict[str, Any]]:
        """Real DOCX→PDF when LibreOffice is available; otherwise HTML→PDF."""
        if ext == "pdf":
            return doc_bytes, {"engine": "passthrough"}
        if ext in ("docx", "xlsx"):
            try:
                from app.services.templates.converter import convert_to, is_available
                if is_available():
                    pdf = convert_to(doc_bytes, source_filename=f"render.{ext}", target="pdf")
                    if pdf:
                        return pdf, {"engine": "libreoffice"}
            except Exception:  # noqa: BLE001
                pass
            return None, {"engine": "none", "reason": f"libreoffice unavailable for {ext}→pdf"}
        if ext in ("html",):
            from app.services.documents.pdf_engine import engine_status, render_pdf
            eng = engine_status()
            if not eng.available:
                return None, {"engine": "none", "reason": eng.error or "no html→pdf engine"}
            return render_pdf(doc_bytes.decode("utf-8", errors="ignore"))
        # XLSX preview-as-PDF is intentionally skipped for now (Phase 4 work).
        return None, {"engine": "none", "reason": f"no pdf converter for ext={ext}"}

    async def _next_number(
        self, session: AsyncSession, company_id: str, *, kind: str,
    ) -> str:
        """Monotonic counter per (company, kind) using Document rows."""
        type_code = _KIND_TO_DOCTYPE.get(kind, "OTHER")
        count = (await session.scalar(
            select(func.count(Document.id)).where(
                Document.company_id == company_id, Document.type == type_code,
            ),
        )) or 0
        prefix = _KIND_TO_NUM_PREFIX.get(kind, "DOC")
        return f"{prefix}-{datetime.utcnow().year}-{count + 1:04d}"

    async def _request_approval(
        self, session: AsyncSession, *,
        company_id: str, document: Document, actor_id: str,
        intent: IntentSpec, document_number: str, quality: QualityReport,
    ) -> tuple[str, str]:
        """Create the approval row, but BLOCK it if QA failed.

        BLOCKED approvals are visible in the queue with the failing issues
        attached; operators cleared the document → can re-submit (or the
        document is regenerated). PENDING approvals follow the normal flow.
        """
        blocking_issues = [i for i in quality.issues if i.severity == "error"]
        is_blocked = quality.status == "blocked" or bool(blocking_issues)
        status = "BLOCKED" if is_blocked else "PENDING"
        summary = (
            ("⛔ BLOCKED — " if is_blocked else "")
            + f"Send {_human_kind(intent.kind)} {document_number}"
            + (f" to {intent.client_name}" if intent.client_name else "")
            + (f" · quality {quality.score}/100" if is_blocked else "")
        )
        ap = Approval(
            id=f"apr_{uuid.uuid4().hex[:10]}",
            company_id=company_id,
            resource_type="document",
            resource_id=document.id,
            action="send_document",
            summary=summary,
            payload={
                "document_id": document.id,
                "kind": intent.kind,
                "number": document_number,
                "client": intent.client_name,
                "total": intent.total,
                "currency": intent.currency,
                "quality_score": quality.score,
                "quality_status": quality.status,
                "blocking_issues": [
                    {"code": i.code, "message": i.message, "where": i.where}
                    for i in blocking_issues
                ],
            },
            status=status, requested_by="ai",
        )
        session.add(ap)
        await session.flush()
        await self.audit.record(
            session, company_id=company_id, actor_type="ai", actor_id=actor_id,
            action="approval.blocked" if is_blocked else "approval.request",
            resource=ap.id,
            meta={
                "document_id": document.id, "action": "send_document",
                "quality_score": quality.score, "quality_status": quality.status,
                "issue_codes": [i.code for i in blocking_issues],
            },
        )
        return ap.id, status


def _human_kind(kind: str) -> str:
    return {
        "invoice": "Счёт",
        "act": "Акт",
        "nakladnaya": "Накладная",
        "contract": "Договор",
        "trust_letter": "Доверенность",
    }.get(kind, "Документ")


