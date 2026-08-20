"""Invoice service — DB-backed, renderer-driven, tenant-scoped."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Company, Invoice
from app.services.audit.logger import AuditLogger
from app.services.documents.render import get_renderer
from app.services.reference_data.matcher import resolve_counterparty
from app.services.storage import get_storage
from app.services.templates.service import TemplateService


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class InvoiceService:
    def __init__(self) -> None:
        self.audit = AuditLogger()
        self.storage = get_storage()
        self.templates = TemplateService()

    # ── reads ──────────────────────────────────────────────────────────────

    async def list(self, session: AsyncSession, company_id: str) -> list[Invoice]:
        rows = await session.scalars(
            select(Invoice).where(Invoice.company_id == company_id).order_by(desc(Invoice.created_at)),
        )
        return list(rows)

    async def get(self, session: AsyncSession, company_id: str, invoice_id: str) -> Invoice | None:
        inv = await session.get(Invoice, invoice_id)
        if not inv or inv.company_id != company_id:
            return None
        return inv

    async def get_with_relations(self, session: AsyncSession, company_id: str, invoice_id: str):
        inv = await self.get(session, company_id, invoice_id)
        if not inv:
            return None, None, None
        company = await session.get(Company, inv.company_id)
        client = await session.get(Client, inv.client_id) if inv.client_id else None
        return inv, company, client

    # ── helpers ────────────────────────────────────────────────────────────

    async def _next_number(self, session: AsyncSession, company: Company) -> str:
        count = await session.scalar(
            select(func.count(Invoice.id)).where(Invoice.company_id == company.id),
        )
        fmt = (company.settings or {}).get("invoice", {}).get("numbering_format", "INV-{year}-{seq:04d}")
        return fmt.format(year=datetime.utcnow().year, seq=(count or 0) + 1)

    async def _pick_template(self, session: AsyncSession, company_id: str, *, kind: str,
                              industry: str | None = None, language: str | None = None):
        """Deterministic template selection. Returns (template_or_None, MatchResult).
        Falls back to the legacy HTML default if no VERIFIED candidate exists."""
        from app.services.templates.matcher import match_best
        m = await match_best(session, company_id=company_id, kind=kind,
                              industry=industry, language=language)
        if m.template:
            return m.template, m
        # Legacy fallback (built-in HTML default) — for new tenants without templates.
        return (await self.templates.get_default(session, company_id, kind)), m

    async def _find_or_create_client(self, session: AsyncSession, company_id: str, name: str) -> Client:
        """Fuzzy-matches via the shared reference_data resolver (also used by
        the AI document pipeline) instead of a bespoke exact/substring scan —
        one matching implementation instead of two that could quietly drift
        apart. A low-confidence match still gets used (same behavior as the
        old substring-based near-duplicate guard did — never blocking invoice
        creation on an ambiguous name), just logged instead of silently
        accepted."""
        resolved = await resolve_counterparty(session, company_id, name)
        if resolved.low_confidence:
            await self.audit.record(
                session, company_id=company_id, actor_type="system",
                action="client.possible_duplicate",
                meta={"new": name, "matched": resolved.record.name, "score": resolved.match_score},
            )
        return resolved.record

    # ── render ─────────────────────────────────────────────────────────────

    async def _render_document(self, session: AsyncSession, invoice: Invoice, company: Company, client: Client) -> tuple[bytes, str, str]:
        # Prefer VERIFIED template via deterministic matcher; fallback to HTML default.
        template, match = await self._pick_template(
            session, company.id, kind="invoice",
            industry=(company.settings or {}).get("industry"),
            language=client and getattr(client, "language", None),
        )
        fmt = template.format if template else "html"
        body = template.body if template else ""

        # Audit match decision so the Activity Center can show which template won/lost.
        await self.audit.record(
            session, company_id=company.id, actor_type="system",
            action="template.matched" if template else "template.missing",
            resource=template.id if template else None,
            meta={"kind": "invoice", "reason": match.reason,
                  "alternatives": [{"id": t.id, "name": t.name, "score": s}
                                    for t, s in (match.alternatives or [])],
                  "score": match.score},
        )

        settings = company.settings or {}
        branding = (settings.get("branding") or {}).copy()
        # Materialize a signed logo URL for embedding (HTML renderer expects a list).
        logo_key = branding.get("logo_key") or company.logo_key
        branding["logo_url_list"] = [{"url": self.storage.presign_get(logo_key, expires_in=3600)}] if logo_key else []
        branding.setdefault("primary_color", "#0f172a")

        context = {
            "company": {"name": company.name, "bin": company.bin or "—"},
            "client":  {"name": client.name, "bin": client.bin or "—", "phone": client.phone or ""},
            "branding": branding,
            "invoice": {
                "number": invoice.number,
                "issue_date": invoice.issue_date.date().isoformat(),
                "due_date":   invoice.due_date.date().isoformat() if invoice.due_date else "—",
                "currency":   invoice.currency,
                "items":      invoice.items,
                "subtotal":   invoice.subtotal,
                "tax_total":  invoice.tax_total,
                "total":      invoice.total,
                "footer_note": (settings.get("invoice") or {}).get("footer_note", ""),
            },
        }
        return get_renderer(fmt).render(body=body, context=context)

    # ── transitions ────────────────────────────────────────────────────────

    async def create_draft(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        client_name: str,
        items: list[dict[str, Any]],
        due_in_days: int | None = None,
        actor_type: str = "ai",
        actor_id: str | None = None,
    ) -> Invoice:
        from app.services.limits.usage import assert_can_create_invoice
        from app.services.context.service import load_context as _load
        await assert_can_create_invoice(session, company_id)
        company = await session.get(Company, company_id)
        if not company:
            raise ValueError("company not found")
        ctx = await _load(session, company_id)
        if due_in_days is None:
            due_in_days = ctx.accounting.due_in_days_default
        # Apply company VAT automatically to any line with tax=0.
        if ctx.accounting.vat_enabled:
            rate = ctx.accounting.vat_percent / 100.0
            items = [
                {**it, "tax": rate} if not it.get("tax") else it
                for it in items
            ]

        client = await self._find_or_create_client(session, company_id, client_name)

        subtotal = sum(Decimal(str(i["qty"])) * Decimal(str(i["price"])) for i in items)
        tax_total = sum(
            Decimal(str(i["qty"])) * Decimal(str(i["price"])) * Decimal(str(i.get("tax", 0)))
            for i in items
        )
        total = subtotal + tax_total

        invoice = Invoice(
            id=_id("inv"),
            company_id=company_id,
            client_id=client.id,
            number=await self._next_number(session, company),
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=due_in_days),
            currency=ctx.accounting.currency_default,
            subtotal=subtotal, tax_total=tax_total, total=total,
            status="DRAFT", items=items,
            notes=f"source={actor_type}",
        )
        session.add(invoice)
        await session.flush()

        body, mime, ext = await self._render_document(session, invoice, company, client)
        key = f"{company_id}/invoices/{invoice.id}/{invoice.number}.{ext}"
        self.storage.put(key, body, content_type=mime)
        invoice.pdf_key = key
        invoice.notes = (invoice.notes or "") + f";source={actor_type}"

        # If we have an HTML render and a PDF engine, render PDF synchronously so
        # the AI assistant can return a download link in the same tool response.
        pdf_url = None
        if mime == "text/html":
            try:
                from app.services.documents.pdf_engine import engine_status, render_pdf
                eng = engine_status()
                if eng.available:
                    pdf_bytes, meta = render_pdf(body.decode("utf-8"))
                    pdf_key = key.rsplit(".", 1)[0] + ".pdf"
                    self.storage.put(pdf_key, pdf_bytes, content_type="application/pdf")
                    pdf_url = self.storage.presign_get(pdf_key, expires_in=3600)
                    invoice.pdf_key = pdf_key   # prefer PDF for downstream actions
                    await self.audit.record(
                        session, company_id=company_id, actor_type="system",
                        action="pdf.generated", resource=invoice.id,
                        meta={"engine": meta["engine"], "duration_ms": meta["duration_ms"],
                              "bytes": meta["bytes"], "via": "ai_create"},
                    )
            except Exception as exc:  # noqa: BLE001
                await self.audit.record(
                    session, company_id=company_id, actor_type="system",
                    action="pdf.failed", resource=invoice.id, meta={"error": str(exc)[:200]},
                )

        # Bump template usage counter for future scoring.
        try:
            from app.services.templates.matcher import bump_success
            from app.db.models import Template
            from sqlalchemy import select, desc
            t = await session.scalar(
                select(Template).where(
                    Template.company_id == company_id, Template.kind == "invoice",
                    Template.status == "VERIFIED",
                ).order_by(desc(Template.last_render_at)).limit(1),
            )
            if t:
                bump_success(t)
        except Exception:  # noqa: BLE001
            pass

        await self.audit.record(
            session, company_id=company_id, actor_type=actor_type, actor_id=actor_id,
            action="invoice.create_draft", resource=invoice.id,
            meta={"number": invoice.number, "total": str(total), "client": client.name,
                  "pdf": bool(pdf_url)},
        )
        invoice._ai_render_meta = {"pdf_url": pdf_url}   # picked up by tool
        return invoice

    # ── guardrails ──────────────────────────────────────────────────────────

    _IMMUTABLE_STATUSES = {"APPROVED", "SENT", "PAID"}

    def assert_mutable(self, invoice: Invoice) -> None:
        """Approved/sent/paid invoices are immutable — modifications create a new doc."""
        if invoice.status in self._IMMUTABLE_STATUSES:
            raise ValueError(f"invoice {invoice.number} is immutable (status={invoice.status})")

    async def retry_send(self, session: AsyncSession, invoice: Invoice) -> Invoice:
        """Retry the WhatsApp send for an invoice that already has owner approval."""
        if invoice.status not in {"SENT", "APPROVED"}:
            raise ValueError("can only retry send on APPROVED or SENT invoices")
        try:
            from app.services.integrations.whatsapp import WhatsAppMessage, build_whatsapp_provider
            provider = await build_whatsapp_provider(session, invoice.company_id)
            doc_url = self.storage.presign_get(invoice.pdf_key, expires_in=3600) if invoice.pdf_key else None
            await provider.send(WhatsAppMessage(
                to="+0", text=f"Invoice {invoice.number} (retry)",
                document_url=doc_url, document_filename=f"{invoice.number}.html",
            ))
            invoice.status = "SENT"
            await self.audit.record(
                session, company_id=invoice.company_id, actor_type="user",
                action="whatsapp.send_pdf", resource=invoice.id,
                meta={"retry": True, "provider": provider.name},
            )
        except Exception as exc:  # noqa: BLE001
            await self.audit.record(
                session, company_id=invoice.company_id, actor_type="system",
                action="whatsapp.send_failed", resource=invoice.id,
                meta={"retry": True, "error": str(exc)},
            )
            raise
        return invoice

    async def mark_pending_approval(self, session: AsyncSession, invoice: Invoice) -> Invoice:
        invoice.status = "PENDING_APPROVAL"
        await self.audit.record(
            session, company_id=invoice.company_id, actor_type="system",
            action="invoice.pending_approval", resource=invoice.id,
        )
        return invoice

    async def mark_approved_and_send(self, session: AsyncSession, invoice: Invoice, *, decided_by: str) -> Invoice:
        invoice.status = "SENT"
        await self.audit.record(
            session, company_id=invoice.company_id, actor_type="user",
            actor_id=decided_by, action="invoice.approved", resource=invoice.id,
        )
        # Send is best-effort; failures don't block the approval transition.
        try:
            from app.services.integrations.whatsapp import WhatsAppMessage, build_whatsapp_provider
            provider = await build_whatsapp_provider(session, invoice.company_id)
            doc_url = self.storage.presign_get(invoice.pdf_key, expires_in=3600) if invoice.pdf_key else None
            await provider.send(WhatsAppMessage(
                to="+0",  # demo — production reads client.phone
                text=f"Invoice {invoice.number} is ready.",
                document_url=doc_url,
                document_filename=f"{invoice.number}.html",
            ))
            await self.audit.record(
                session, company_id=invoice.company_id, actor_type="system",
                action="whatsapp.send_pdf", resource=invoice.id,
                meta={"provider": provider.name},
            )
        except Exception as exc:  # noqa: BLE001
            await self.audit.record(
                session, company_id=invoice.company_id, actor_type="system",
                action="whatsapp.send_failed", resource=invoice.id,
                meta={"error": str(exc)},
            )
        return invoice

    async def mark_rejected(self, session: AsyncSession, invoice: Invoice, *, decided_by: str) -> Invoice:
        invoice.status = "CANCELLED"
        await self.audit.record(
            session, company_id=invoice.company_id, actor_type="user",
            actor_id=decided_by, action="invoice.rejected", resource=invoice.id,
        )
        return invoice
