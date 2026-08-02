"""Realistic Kazakhstan demo dataset — makes the app feel alive on first login.

Idempotent — checks the audit log for the seed marker before reseeding.

Seeds (per company):
  * 8 KZ counterparties with realistic names, BINs, phones
  * 14 invoices across DRAFT/PENDING_APPROVAL/SENT/PAID/OVERDUE/CANCELLED
  * 3 generated documents (act, nakladnaya, invoice) — incl. one BLOCKED by QA
  * 2 standalone Approvals (one PENDING, one BLOCKED) with quality payload
  * 5 uploaded source documents in varied OCR states (including one FAILED)
  * 25+ audit breadcrumbs covering WhatsApp → AI → approval → send cycles
  * 2 AI Conversations with realistic message threads (RU/EN)
  * 1 workflow failure (Kaspi auth) seeded into Recovery Center

Goal: dashboard, recovery, approvals, documents, and activity all look
operational immediately on first login — no empty screens.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Approval, AuditLog, Client, Conversation, Document, Invoice, Message,
)
from app.services.audit.logger import AuditLogger
from app.services.invoices.service import InvoiceService

_MARKER = "demo.seeded.v2"


def _id(p: str) -> str:
    return f"{p}_{uuid.uuid4().hex[:10]}"


async def seed_demo(session: AsyncSession, *, company_id: str, actor_id: str) -> dict:
    # Skip when already seeded with current marker. Older v1 marker is left
    # in place so re-running on existing data is harmless.
    if await session.scalar(
        select(AuditLog).where(AuditLog.company_id == company_id, AuditLog.action == _MARKER),
    ):
        return {"already_seeded": True}

    audit = AuditLogger()
    invoices = InvoiceService()
    now = datetime.utcnow()

    # Demo company should always be on a permissive plan — the Free quota
    # would block the volume of seed data we're about to insert. This is
    # cosmetic only (no Stripe), reversible from /settings.
    from app.db.models import Company as _Company
    _co = await session.get(_Company, company_id)
    if _co and _co.plan == "free":
        _co.plan = "business"
        await session.flush()

    # ── 1. Counterparties — realistic KZ businesses ────────────────────────
    base_clients = [
        ("TOO Сапа Logistics",   "010140000123", "+7 701 234 5601"),
        ("ИП Аманжолов А.Е.",    "880612350789", "+7 705 887 4422"),
        ("TOO KazSteel Industry","050315000456", "+7 727 244 8800"),
        ("АО Алматы Кофе",       "100925000111", "+7 727 311 0900"),
        ("ТОО ТехноСервис KZ",   "061205000222", "+7 700 654 1212"),
        ("ИП Жумабаева Ж.К.",    "900318401234", "+7 707 145 9988"),
        ("TOO Astana Construct", "030712000333", "+7 717 232 4477"),
        ("TOO Caspian Trade",    "200401000444", "+7 728 555 6010"),
    ]
    name_to_client: dict[str, Client] = {}
    for name, bin_, phone in base_clients:
        existing = await session.scalar(
            select(Client).where(Client.company_id == company_id, Client.name == name),
        )
        if existing:
            name_to_client[name] = existing
            continue
        c = Client(id=_id("cl"), company_id=company_id, name=name, bin=bin_, phone=phone)
        session.add(c)
        name_to_client[name] = c
    await session.flush()

    # ── 2. Invoices in varied lifecycle states ─────────────────────────────
    scenarios = [
        # (client,                     items,                                         status,             days_offset)
        ("TOO Сапа Logistics",   [("Logistics services — May", 1, 1_240_000, 0.12)],  "PAID",     -35),
        ("ИП Аманжолов А.Е.",    [("Consulting hours", 12, 18_000, 0.12)],            "PAID",     -28),
        ("TOO KazSteel Industry",[("Steel rolls Q2 order", 1, 4_650_000, 0.12)],      "PAID",     -24),
        ("АО Алматы Кофе",       [("Coffee beans 50kg", 50, 4_200, 0.12)],            "SENT",     -10),
        ("TOO Сапа Logistics",   [("Freight to Almaty",  1, 320_000, 0.12)],          "SENT",     -7),
        ("ТОО ТехноСервис KZ",   [("Server maintenance May", 1, 180_000, 0.12)],      "SENT",     -4),
        ("ИП Жумабаева Ж.К.",    [("Design retainer", 1, 250_000, 0.0)],              "SENT",     -2),
        ("TOO Astana Construct", [("Material delivery",  3, 95_000, 0.12)],           "OVERDUE",  -45),
        ("TOO Caspian Trade",    [("Customs brokerage",  1, 145_000, 0.12)],          "OVERDUE",  -32),
        ("АО Алматы Кофе",       [("Espresso machine repair", 1, 88_000, 0.12)],      "PENDING_APPROVAL", -1),
        ("TOO KazSteel Industry",[("Inspection report",  1, 540_000, 0.12)],          "DRAFT",    0),
        ("TOO Сапа Logistics",   [("July retainer (preview)", 1, 1_200_000, 0.12)],   "DRAFT",    0),
        ("ИП Аманжолов А.Е.",    [("Q1 consulting (rebill)", 8, 18_000, 0.12)],       "CANCELLED", -55),
        ("TOO Caspian Trade",    [("Delivery — return", 1, 30_000, 0.0)],             "PAID",     -50),
    ]
    created: list[Invoice] = []
    for client_name, items, status, days_offset in scenarios:
        invoice = await invoices.create_draft(
            session, company_id=company_id, client_name=client_name,
            items=[{"name": n, "qty": q, "price": p, "tax": t} for (n, q, p, t) in items],
            actor_type="system", actor_id="demo",
        )
        invoice.issue_date = now + timedelta(days=days_offset)
        invoice.due_date = invoice.issue_date + timedelta(days=14)
        invoice.status = status
        created.append(invoice)

    # ── 3. Generated documents (acts, nakladnaya, with quality records) ────
    # We don't render actual files in the seeder — instead we register them
    # as `GENERATED` Document rows with parsed=quality payloads so the UI's
    # diagnostics surfaces light up immediately.
    generated_specs = [
        {
            "type": "ACT", "title": "Акт ACT-2026-0001 — TOO Сапа Logistics",
            "client": "TOO Сапа Logistics", "kind": "act",
            "quality_score": 96, "quality_status": "ok",
            "fallback_used": False, "adaptation_anchors": 4,
            "template_name": "Акт выполненных работ (KZ)", "issues": [],
        },
        {
            "type": "NAKLADNAYA", "title": "Накладная NKL-2026-0001 — TOO KazSteel",
            "client": "TOO KazSteel Industry", "kind": "nakladnaya",
            "quality_score": 78, "quality_status": "warning",
            "fallback_used": False, "adaptation_anchors": 2,
            "template_name": "Накладная (склад)",
            "issues": [
                {"code": "empty_table_row", "severity": "warning", "weight": 2,
                 "message": "Table 1 contains an empty row (repeating-row template not consumed?).",
                 "where": "table 1", "stage": "quality"},
                {"code": "anchor_ambiguous", "severity": "warning", "weight": 5,
                 "message": "Label 'Адрес' (table 0 row 2): neighbour cell has existing content — not overwriting.",
                 "stage": "adaptation"},
            ],
        },
        {
            "type": "ACT", "title": "Акт ACT-2026-0002 — ИП Аманжолов",
            "client": "ИП Аманжолов А.Е.", "kind": "act",
            "quality_score": 48, "quality_status": "blocked",
            "fallback_used": True, "fallback_reason": "no_verified_template_for_act",
            "template_name": None, "adaptation_anchors": 0,
            "issues": [
                {"code": "missing_client_bin", "severity": "error", "weight": 20,
                 "message": "Client BIN is empty in the populated context.", "stage": "quality"},
                {"code": "pdf_export_skipped", "severity": "warning", "weight": 5,
                 "message": "PDF export skipped: WeasyPrint native libs unavailable.",
                 "stage": "pdf_export"},
                {"code": "no_verified_template", "severity": "warning", "weight": 3,
                 "message": "No VERIFIED template for kind=act. Falling back to built-in HTML.",
                 "stage": "match",
                 "suggested_fix": "Upload a DOCX template and run the mapping wizard until VERIFIED."},
            ],
        },
    ]
    for idx, spec in enumerate(generated_specs):
        doc_key = f"{company_id}/generated/demo_{idx}/preview.pdf"
        diag = [
            {"stage": "intent", "code": "intent_parsed", "severity": "info",
             "message": f"Parsed intent: kind={spec['kind']} client='{spec['client']}'."},
            ({"stage": "match", "code": "template_matched", "severity": "info",
              "message": f"Matched template '{spec['template_name']}'."}
             if spec["template_name"] else
             {"stage": "match", "code": "no_verified_template", "severity": "warning",
              "message": "No VERIFIED template — falling back to built-in HTML.",
              "suggested_fix": "Upload a DOCX template and run the mapping wizard."}),
            *(([{"stage": "adaptation", "code": "anchor_injected", "severity": "info",
                "message": f"Injected {spec['adaptation_anchors']} canonical anchor(s) into legacy template."}]
              ) if spec["adaptation_anchors"] else []),
            *spec["issues"],
        ]
        session.add(Document(
            id=_id("gen"), company_id=company_id, type=spec["type"], title=spec["title"],
            storage_key=doc_key, mime="application/pdf", size=120_000,
            status="GENERATED",
            parsed={
                "generated_by": "ai", "kind": spec["kind"],
                "template": ({"name": spec["template_name"]} if spec["template_name"] else None),
                "adaptation": {"applied": bool(spec["adaptation_anchors"]),
                                "anchors_injected": spec["adaptation_anchors"]},
                "fallback":   {"used": spec["fallback_used"],
                                "reason": spec.get("fallback_reason"),
                                "engine": "html_fallback" if spec["fallback_used"] else None},
                "quality":    {"score": spec["quality_score"], "status": spec["quality_status"],
                                "blocking": spec["quality_status"] == "blocked",
                                "issues": spec["issues"], "issue_count": len(spec["issues"])},
                "diagnostics": diag,
            },
            meta={"warnings": [i["message"] for i in spec["issues"] if i["severity"] == "error"],
                   "quality_status": spec["quality_status"],
                   "quality_score": spec["quality_score"],
                   "fallback_used": spec["fallback_used"]},
            created_by="demo",
        ))

    # ── 4. Approvals — pending and BLOCKED with quality payload ────────────
    pending_target = next(i for i in created if i.status == "PENDING_APPROVAL")
    approval_pending = Approval(
        id=_id("apr"), company_id=company_id, resource_type="invoice",
        resource_id=pending_target.id, action="send_invoice",
        summary=f"Send invoice {pending_target.number} ({pending_target.total} {pending_target.currency})",
        payload={"invoice_id": pending_target.id, "number": pending_target.number,
                  "total": str(pending_target.total), "currency": pending_target.currency},
        status="PENDING", requested_by="ai",
    )
    session.add(approval_pending)

    # BLOCKED approval attached to the generated act with score=48
    blocked_doc_id = _id("apr")
    approval_blocked = Approval(
        id=blocked_doc_id, company_id=company_id, resource_type="document",
        resource_id="gen_demo_blocked",  # standalone — UI shows blocking_issues even without resource
        action="send_document",
        summary="⛔ BLOCKED — Send Акт ACT-2026-0002 to ИП Аманжолов · quality 48/100",
        payload={
            "kind": "act", "number": "ACT-2026-0002", "client": "ИП Аманжолов А.Е.",
            "total": 540000, "currency": "KZT",
            "quality_score": 48, "quality_status": "blocked",
            "blocking_issues": [
                {"code": "missing_client_bin", "where": None,
                 "message": "Client BIN is empty in the populated context."},
            ],
        },
        status="BLOCKED", requested_by="ai",
    )
    session.add(approval_blocked)

    # Mark a previously-decided approval too, so the "Recently decided"
    # section is populated.
    paid_invoice = next(i for i in created if i.status == "PAID")
    session.add(Approval(
        id=_id("apr"), company_id=company_id, resource_type="invoice",
        resource_id=paid_invoice.id, action="send_invoice",
        summary=f"Send invoice {paid_invoice.number}",
        payload={"invoice_id": paid_invoice.id},
        status="APPROVED", requested_by="ai", decided_by=actor_id,
        decided_at=now - timedelta(days=20),
    ))

    # ── 5. Uploaded source documents — varied OCR states ───────────────────
    docs = [
        ("Договор поставки — TOO Сапа.pdf",       "PDF", "application/pdf",
         "PARSED",
         {"counterparty": "TOO Сапа Logistics", "amount": "1 240 000 KZT",
          "date": (now - timedelta(days=30)).date().isoformat()}),
        ("Счёт от TOO KazSteel.pdf",               "PDF", "application/pdf",
         "PARSED",
         {"number": "KS-2026-118", "total": "4 650 000",
          "supplier": "TOO KazSteel Industry"}),
        ("Накладная — Алматы Кофе (May).jpg",     "IMAGE", "image/jpeg",
         "OCR_DONE",
         {"counterparty": "АО Алматы Кофе",
          "ocr_confidence": 0.81}),
        ("Bank statement Kaspi April.pdf",        "PDF", "application/pdf",
         "PARSED",
         {"bank": "Kaspi Gold", "period": "2026-04", "txn_count": 47}),
        ("scan_blurry_invoice.jpg",                "IMAGE", "image/jpeg",
         "FAILED",
         {"error": "OCR confidence below threshold (0.31)",
          "suggested_fix": "Re-photograph the document in better lighting "
                            "or upload the PDF original."}),
    ]
    for title, dtype, mime, status, parsed in docs:
        session.add(Document(
            id=_id("doc"), company_id=company_id, type=dtype, title=title,
            storage_key=f"{company_id}/documents/demo/{title}", mime=mime,
            size=128_000, status=status, parsed=parsed,
            meta={"demo": True}, created_by="demo",
        ))

    # ── 6. AI conversations — make the assistant feel used ─────────────────
    conv1_id = _id("conv")
    session.add(Conversation(
        id=conv1_id, company_id=company_id, user_id=actor_id,
        title="Создание акта для TOO Сапа Logistics",
        created_at=now - timedelta(days=1, hours=3),
    ))
    conv1_msgs = [
        ("user",      "Создай акт для TOO Сапа Logistics на 1 240 000 KZT за майскую логистику."),
        ("assistant", "Сгенерировал акт ACT-2026-0001. Шаблон: «Акт выполненных работ (KZ)». "
                      "Quality 96/100. PDF готов, approval отправлен на согласование."),
        ("user",      "Покажи последние неоплаченные счета."),
        ("assistant", "Просрочены: INV-2026-0008 (TOO Astana Construct, 285 000 KZT, 45 дней) "
                      "и INV-2026-0009 (TOO Caspian Trade, 145 000 KZT, 32 дня). "
                      "Хочешь отправить напоминания по WhatsApp?"),
    ]
    for role, content in conv1_msgs:
        session.add(Message(conversation_id=conv1_id, role=role, content=content,
                              created_at=now - timedelta(days=1, hours=3, minutes=-len(role))))

    conv2_id = _id("conv")
    session.add(Conversation(
        id=conv2_id, company_id=company_id, user_id=actor_id,
        title="Проверка квартальной отчётности",
        created_at=now - timedelta(hours=5),
    ))
    for role, content in [
        ("user",      "Сравни выручку за апрель и май."),
        ("assistant", "Апрель: 6 480 000 KZT (12 счетов). Май: 7 920 000 KZT (14 счетов, +22%). "
                      "Основной рост — TOO KazSteel Industry (+1 200 000)."),
    ]:
        session.add(Message(conversation_id=conv2_id, role=role, content=content,
                              created_at=now - timedelta(hours=5)))

    # ── 7. Audit breadcrumbs — operational timeline ────────────────────────
    breadcrumbs: list[tuple[str, str, str | None, dict]] = [
        ("system", "whatsapp.inbound",        None,           {"from": "+7 701 234 5601", "text": "Нужен счёт на майские услуги"}),
        ("ai",     "ai.intent_parsed",        None,           {"intent": "create_invoice", "confidence": 0.94, "client": "TOO Сапа Logistics"}),
        ("ai",     "invoice.create_draft",    created[0].id,   {"client": "TOO Сапа Logistics", "total": "1240000"}),
        ("user",   "approval.decide",         created[0].id,   {"approve": True}),
        ("system", "whatsapp.send_pdf",       created[0].id,   {"provider": "meta_cloud"}),
        ("system", "invoice.paid",            created[0].id,   {"method": "kaspi"}),

        ("ai",     "document.generated",      "gen_demo_0",    {"kind": "act", "number": "ACT-2026-0001", "quality_score": 96}),
        ("ai",     "approval.request",        approval_pending.id, {"resource": pending_target.id}),

        ("ai",     "document.generated",      "gen_demo_2",    {"kind": "act", "number": "ACT-2026-0002", "quality_score": 48, "fallback": True}),
        ("ai",     "approval.blocked",        blocked_doc_id,  {"quality_score": 48, "issue_codes": ["missing_client_bin"]}),

        ("system", "workflow.run_started",    "wf_kaspi_recon",{"trigger": "cron.daily"}),
        ("system", "workflow.run_failed",     "wf_kaspi_recon",{"step": "kaspi.fetch_payouts", "error": "auth: 401",
                                                                "suggested_fix": "Refresh Kaspi API token in /integrations."}),

        ("user",   "document.upload",         None,           {"name": "Договор поставки — TOO Сапа.pdf"}),
        ("system", "document.parsed",         None,           {"counterparty": "TOO Сапа Logistics", "confidence": 0.94}),
        ("user",   "document.upload",         None,           {"name": "scan_blurry_invoice.jpg"}),
        ("system", "document.failed",         None,           {"error": "OCR confidence 0.31 below threshold"}),

        ("system", "invoice.overdue",         created[7].id,   {"days": 45, "client": "TOO Astana Construct"}),
        ("system", "invoice.overdue",         created[8].id,   {"days": 32, "client": "TOO Caspian Trade"}),

        ("ai",     "ai.tool_invoked",         None,           {"tool": "generate_document", "danger": "financial"}),
        ("ai",     "ai.tool_invoked",         None,           {"tool": "list_invoices",     "danger": "read"}),
    ]
    for actor_type, action, resource, meta in breadcrumbs:
        await audit.record(
            session, company_id=company_id, actor_type=actor_type,
            actor_id=actor_id if actor_type == "user" else None,
            action=action, resource=resource, meta=meta,
        )

    await audit.record(session, company_id=company_id, actor_type="system",
                        action=_MARKER, meta={"at": now.isoformat()})
    await session.flush()
    return {
        "already_seeded": False,
        "clients":       len(base_clients),
        "invoices":      len(created),
        "generated_documents": len(generated_specs),
        "approvals":     3,
        "documents":     len(docs),
        "conversations": 2,
        "audit_events":  len(breadcrumbs),
    }
