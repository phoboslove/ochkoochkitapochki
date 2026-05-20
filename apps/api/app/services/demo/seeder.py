"""Realistic demo data — populates a company so the app feels alive on first login.

Creates: invoices in mixed states, a pending approval, a failed workflow run
audit trail, OCR-parsed documents, overdue invoices, simulated WhatsApp inbound.
Idempotent — checks the audit log for a marker before reseeding.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Approval, AuditLog, Client, Document, Invoice
from app.services.audit.logger import AuditLogger
from app.services.invoices.service import InvoiceService

_MARKER = "demo.seeded"


def _id(p: str) -> str:
    return f"{p}_{uuid.uuid4().hex[:10]}"


async def seed_demo(session: AsyncSession, *, company_id: str, actor_id: str) -> dict:
    if await session.scalar(
        select(AuditLog).where(AuditLog.company_id == company_id, AuditLog.action == _MARKER),
    ):
        return {"already_seeded": True}

    audit = AuditLogger()
    invoices = InvoiceService()

    # 1. Counterparties
    base_clients = [
        ("TOO ABC",    "123456789012", "+7 701 000 0001"),
        ("ИП Иванов",  "987654321098", "+7 705 000 0002"),
        ("TOO Beta",   "555555555555", "+7 707 000 0003"),
        ("TOO Gamma",  "111122223333", "+7 700 000 0004"),
        ("TOO Delta",  "444455556666", "+7 702 000 0005"),
    ]
    for name, bin_, phone in base_clients:
        existing = await session.scalar(
            select(Client).where(Client.company_id == company_id, Client.name == name),
        )
        if not existing:
            session.add(Client(id=_id("cl"), company_id=company_id, name=name, bin=bin_, phone=phone))
    await session.flush()

    now = datetime.utcnow()

    # 2. Invoices in varied states (some paid, some sent, one overdue, one draft, one pending approval)
    scenarios = [
        ("TOO ABC",   850_000, "PAID",    -22),
        ("ИП Иванов", 120_000, "PAID",    -19),
        ("TOO Beta",  540_000, "OVERDUE", -34),  # overdue
        ("TOO Gamma", 310_000, "SENT",    -3),
        ("TOO Delta", 220_000, "SENT",    -1),
        ("TOO ABC",   180_000, "DRAFT",    0),
    ]
    created_invoices: list[Invoice] = []
    for client_name, amount, status, days_offset in scenarios:
        invoice = await invoices.create_draft(
            session, company_id=company_id,
            client_name=client_name,
            items=[{"name": "Services", "qty": 1, "price": amount, "tax": 0}],
            actor_type="system", actor_id="demo",
        )
        invoice.issue_date = now + timedelta(days=days_offset)
        invoice.due_date = invoice.issue_date + timedelta(days=14)
        invoice.status = status
        created_invoices.append(invoice)

    # 3. One pending approval (the latest draft — flips to PENDING_APPROVAL)
    pending_target = created_invoices[-1]
    approval = Approval(
        id=_id("apr"), company_id=company_id, resource_type="invoice",
        resource_id=pending_target.id, action="send_invoice",
        summary=f"Send invoice {pending_target.number} ({pending_target.total} {pending_target.currency})",
        payload={"invoice_id": pending_target.id, "number": pending_target.number},
        status="PENDING", requested_by="ai",
    )
    session.add(approval)
    pending_target.status = "PENDING_APPROVAL"

    # 4. Realistic audit-log breadcrumbs (gives the timeline + activity feed life)
    breadcrumbs = [
        ("system", "whatsapp.inbound",        None,                  {"from": "+7 701 000 0001", "text": "Need invoice for 850k"}),
        ("ai",     "ai.intent_parsed",        None,                  {"intent": "create_invoice", "confidence": 0.94}),
        ("ai",     "invoice.create_draft",    created_invoices[0].id, {"client": "TOO ABC"}),
        ("user",   "approval.decide",         created_invoices[0].id, {"approve": True}),
        ("system", "whatsapp.send_pdf",       created_invoices[0].id, {"provider": "meta_cloud"}),
        ("system", "workflow.run_started",    "wf_whatsapp_invoice", {"trigger": "whatsapp.message"}),
        ("system", "workflow.run_failed",     "wf_kaspi_recon",      {"step": "kaspi.fetch_payouts", "error": "auth: 401"}),
        ("ai",     "approval.request",        approval.id,           {"resource": pending_target.id}),
        ("user",   "document.upload",         None,                  {"name": "Contract — TOO ABC.pdf"}),
        ("system", "document.parsed",         None,                  {"counterparty": "TOO ABC"}),
    ]
    for actor_type, action, resource, meta in breadcrumbs:
        await audit.record(
            session, company_id=company_id, actor_type=actor_type,
            actor_id=actor_id if actor_type == "user" else None,
            action=action, resource=resource, meta=meta,
        )

    # 5. Documents (already-parsed entries — no actual file bytes needed for demo)
    docs = [
        ("Contract — TOO ABC.pdf", "PDF", "application/pdf", "PARSED",
         {"counterparty": "TOO ABC", "amount": "1,200,000 KZT"}),
        ("Invoice INV-2025-014.pdf", "PDF", "application/pdf", "PARSED",
         {"number": "INV-2025-014", "total": "850000"}),
        ("Act #2025-04-30.docx", "DOCX",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "OCR_DONE",
         {"counterparty": "ИП Иванов"}),
        ("scan_blurry.jpg", "IMAGE", "image/jpeg", "FAILED",
         {"error": "OCR confidence below threshold"}),
    ]
    for title, dtype, mime, status, parsed in docs:
        session.add(Document(
            id=_id("doc"), company_id=company_id, type=dtype, title=title,
            storage_key=f"{company_id}/documents/demo/{title}", mime=mime,
            size=42_000, status=status, parsed=parsed,
            meta={"demo": True}, created_by="demo",
        ))

    await audit.record(session, company_id=company_id, actor_type="system",
                       action=_MARKER, meta={"at": now.isoformat()})
    await session.flush()
    return {"already_seeded": False, "invoices": len(created_invoices), "approvals": 1, "documents": len(docs)}
