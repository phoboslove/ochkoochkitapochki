from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.db.models import Invoice
from app.services.invoices.service import InvoiceService
from app.services.storage.base import sign_local_url

router = APIRouter()
service = InvoiceService()


def _serialize(inv: Invoice) -> dict:
    return {
        "id": inv.id, "number": inv.number, "client_id": inv.client_id,
        "issue_date": inv.issue_date.date().isoformat() if inv.issue_date else None,
        "due_date":   inv.due_date.date().isoformat() if inv.due_date else None,
        "currency": inv.currency,
        "subtotal": str(inv.subtotal), "tax_total": str(inv.tax_total), "total": str(inv.total),
        "status": inv.status, "items": inv.items,
        "pdf_key": inv.pdf_key,
        "pdf_url": sign_local_url(inv.pdf_key, expires_in=3600) if inv.pdf_key else None,
    }


class InvoiceLine(BaseModel):
    name: str
    qty: float = 1
    price: float
    tax: float = 0


class CreateInvoiceIn(BaseModel):
    client_name: str
    items: list[InvoiceLine]
    due_in_days: int | None = None
    request_send: bool = True


@router.get("")
async def list_invoices(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await service.list(session, user.company_id)
    return [_serialize(r) for r in rows]


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    inv, company, client = await service.get_with_relations(session, user.company_id, invoice_id)
    if not inv:
        raise HTTPException(404, "invoice not found")
    return {
        **_serialize(inv),
        "company": {"name": company.name, "bin": company.bin} if company else None,
        "client": {"id": client.id, "name": client.name, "bin": client.bin, "phone": client.phone} if client else None,
    }


@router.post("/{invoice_id}/pdf")
async def export_pdf(
    invoice_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Render the invoice HTML into a real PDF and persist it.

    Engine selection is automatic (WeasyPrint preferred → xhtml2pdf fallback).
    Failures are audited as `pdf.failed` and surface in Recovery Center.
    """
    from app.services.documents.pdf_engine import engine_status, render_pdf
    from app.services.storage import get_storage
    from app.services.storage.base import sign_local_url
    from app.services.audit.logger import AuditLogger

    inv = await service.get(session, user.company_id, invoice_id)
    if not inv: raise HTTPException(404, "invoice not found")
    if not inv.pdf_key: raise HTTPException(400, "invoice has no rendered HTML yet")

    eng = engine_status()
    if not eng.available:
        await AuditLogger().record(
            session, company_id=user.company_id, actor_type="system",
            action="pdf.failed", resource=inv.id,
            meta={"reason": "engine_unavailable", "error": eng.error},
        )
        await session.commit()
        raise HTTPException(503, eng.error or "no PDF engine available")

    storage = get_storage()
    try:
        html_bytes = storage.get(inv.pdf_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(404, f"source HTML missing: {exc}")
    try:
        pdf_bytes, meta = render_pdf(html_bytes.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        await AuditLogger().record(
            session, company_id=user.company_id, actor_type="system",
            action="pdf.failed", resource=inv.id,
            meta={"engine": eng.name, "error": str(exc)[:200]},
        )
        await session.commit()
        raise HTTPException(500, f"PDF render failed [{eng.name}]: {exc}")

    pdf_key = inv.pdf_key.rsplit(".", 1)[0] + ".pdf"
    storage.put(pdf_key, pdf_bytes, content_type="application/pdf")
    await AuditLogger().record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="pdf.generated", resource=inv.id,
        meta={"engine": meta["engine"], "duration_ms": meta["duration_ms"],
              "bytes": meta["bytes"]},
    )
    await session.commit()
    return {
        "pdf_url": sign_local_url(pdf_key, expires_in=3600),
        "bytes":   meta["bytes"],
        "engine":  meta["engine"],
        "duration_ms": meta["duration_ms"],
    }


@router.post("/pdf-stress-test")
async def pdf_stress_test(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Run a battery of synthetic invoice renders against the active PDF engine.
    Returns a per-scenario report — no DB writes, no storage persistence.
    """
    from app.services.documents.pdf_engine import engine_status, render_pdf
    from app.services.documents.render import get_renderer

    eng = engine_status()
    if not eng.available:
        raise HTTPException(503, eng.error or "no PDF engine available")

    scenarios = [
        ("single_row",        1,  "Service",                                       300_000),
        ("ten_rows",         10,  "Consulting hour",                                12_500),
        ("fifty_rows",       50,  "Line item",                                       4_200),
        ("long_names",       12,
            "Услуги по бухгалтерскому сопровождению и налоговому консультированию за период с 01.01 по 31.12",
            85_000),
        ("multiline",         8,
            "Поставка оборудования\nс монтажом и пусконаладкой\nс гарантией 12 месяцев",
            450_000),
        ("huge_total",        3,  "Premium contract",                          12_500_000),
        ("zero_rows",         0,  "—",                                                  0),
        ("vat_block",        10,  "Materials (VAT 12%)",                          250_000),
    ]
    LONG_COMPANY = ("Товарищество с ограниченной ответственностью "
                    "«Большая Большая Строительная Корпорация Алматы»")
    LONG_CLIENT  = "ИП Жакулов-Тоғышбаев Сабиржан Бекболатұлы"

    html_renderer = get_renderer("html")
    results: list[dict] = []
    for name, n_rows, item_label, price in scenarios:
        items = [{"name": item_label, "qty": 1 + (i % 3),
                  "price": price, "total": price * (1 + (i % 3))} for i in range(n_rows)]
        subtotal = sum(it["total"] for it in items)
        ctx = {
            "company": {"name": LONG_COMPANY if name == "long_names" else "TOO Demo",
                        "bin": "123456789012"},
            "client":  {"name": LONG_CLIENT if name == "long_names" else "TOO ABC",
                        "bin": "987654321098", "phone": "+7 701 000 0001"},
            "branding": {"primary_color": "#0f172a", "logo_url_list": []},
            "invoice": {
                "number": f"STRESS-{name}", "issue_date": "2026-05-19",
                "due_date": "2026-06-02", "currency": "KZT",
                "items": items, "subtotal": subtotal,
                "tax_total": int(subtotal * 0.12) if name == "vat_block" else 0,
                "total": subtotal + (int(subtotal * 0.12) if name == "vat_block" else 0),
                "footer_note": "Stress test render — not a real document.",
            },
        }
        try:
            html_bytes, _mime, _ext = html_renderer.render(body="", context=ctx)
            pdf_bytes, meta = render_pdf(html_bytes.decode("utf-8"))
            ok = pdf_bytes.startswith(b"%PDF") and len(pdf_bytes) > 800
            results.append({
                "scenario": name, "rows": n_rows, "ok": ok,
                "bytes": meta["bytes"], "duration_ms": meta["duration_ms"],
                "engine": meta["engine"],
                "warning": None if ok else "PDF output too small / missing header",
            })
        except Exception as exc:  # noqa: BLE001
            results.append({"scenario": name, "rows": n_rows, "ok": False,
                            "error": str(exc).splitlines()[0][:200]})

    ok = sum(1 for r in results if r.get("ok"))
    return {
        "engine": eng.name, "engine_notes": eng.notes,
        "total": len(results), "passed": ok, "failed": len(results) - ok,
        "scenarios": results,
    }


@router.post("/{invoice_id}/retry-send")
async def retry_send(
    invoice_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    inv = await service.get(session, user.company_id, invoice_id)
    if not inv:
        raise HTTPException(404, "invoice not found")
    try:
        await service.retry_send(session, inv)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"send failed: {e}")
    await session.commit()
    return _serialize(inv)


@router.post("")
async def create_invoice(
    body: CreateInvoiceIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.services.approvals.service import ApprovalService

    invoice = await service.create_draft(
        session, company_id=user.company_id,
        client_name=body.client_name,
        items=[i.model_dump() for i in body.items],
        due_in_days=body.due_in_days,
        actor_type="user", actor_id=user.id,
    )
    out = _serialize(invoice)
    if body.request_send:
        approval = await ApprovalService().request_invoice_send(session, invoice=invoice, requested_by=user.id)
        out["approval_id"] = approval.id
    await session.commit()
    return out
