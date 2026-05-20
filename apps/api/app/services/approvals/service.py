"""Approval service — DB-backed gate for state-changing actions."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Approval, Invoice
from app.services.audit.logger import AuditLogger
from app.services.invoices.service import InvoiceService


def _id() -> str:
    return f"apr_{uuid.uuid4().hex[:10]}"


class ApprovalService:
    def __init__(self) -> None:
        self.audit = AuditLogger()
        self.invoices = InvoiceService()

    async def list(self, session: AsyncSession, company_id: str, *, status: str | None = None) -> list[Approval]:
        q = select(Approval).where(Approval.company_id == company_id)
        if status:
            q = q.where(Approval.status == status)
        rows = await session.scalars(q.order_by(desc(Approval.created_at)))
        return list(rows)

    async def get(self, session: AsyncSession, approval_id: str) -> Approval | None:
        return await session.get(Approval, approval_id)

    async def _notify_admins(self, session: AsyncSession, approval: Approval) -> None:
        """Best-effort multi-channel notification of admins. Never fails the request."""
        try:
            from app.services.integrations.telegram import InlineButton
            from app.services.integrations.telegram.service import notify_admins
            await notify_admins(
                session, company_id=approval.company_id,
                text=f"⏳ *Approval requested*\n{approval.summary}",
                buttons=[[
                    InlineButton(text="✅ Approve", callback_data=f"approve:{approval.id}"),
                    InlineButton(text="❌ Reject",  callback_data=f"reject:{approval.id}"),
                ]],
            )
        except Exception:  # noqa: BLE001
            pass

    async def _rules(self, session: AsyncSession, company_id: str):
        from app.services.context.service import load_context
        ctx = await load_context(session, company_id)
        return ctx.approvals

    async def request_invoice_send(
        self, session: AsyncSession, *, invoice: Invoice, requested_by: str = "ai",
    ) -> Approval:
        rules = await self._rules(session, invoice.company_id)
        # Auto-send if rules allow and amount is below threshold (and not high-value).
        if rules.auto_send_invoices and (
            rules.invoice_amount_threshold <= 0 or float(invoice.total) <= rules.invoice_amount_threshold
        ) and float(invoice.total) < rules.high_value_threshold:
            await self.invoices.mark_approved_and_send(session, invoice, decided_by="system:auto")
            await self.audit.record(
                session, company_id=invoice.company_id, actor_type="system",
                action="approval.auto_sent", resource=invoice.id,
                meta={"reason": "below threshold", "total": str(invoice.total)},
            )
            # Synthesize an APPROVED record so the UI shows the action history.
            approval = Approval(
                id=_id(), company_id=invoice.company_id, resource_type="invoice",
                resource_id=invoice.id, action="send_invoice",
                summary=f"Auto-sent {invoice.number} (below threshold)",
                payload={"invoice_id": invoice.id, "auto": True},
                status="APPROVED", requested_by=requested_by, decided_by="system:auto",
                decided_at=datetime.utcnow(),
            )
            session.add(approval)
            await session.flush()
            return approval
        approval = Approval(
            id=_id(),
            company_id=invoice.company_id,
            resource_type="invoice",
            resource_id=invoice.id,
            action="send_invoice",
            summary=f"Send invoice {invoice.number} ({invoice.total} {invoice.currency})",
            payload={"invoice_id": invoice.id, "number": invoice.number, "total": str(invoice.total)},
            status="PENDING",
            requested_by=requested_by,
        )
        session.add(approval)
        await self.invoices.mark_pending_approval(session, invoice)
        await self.audit.record(
            session, company_id=invoice.company_id, actor_type=requested_by,
            action="approval.request", resource=approval.id,
            meta={"invoice_id": invoice.id, "action": "send_invoice"},
        )
        await session.flush()
        await self._notify_admins(session, approval)
        return approval

    async def decide(
        self, session: AsyncSession, approval_id: str, *, approve: bool, decided_by: str,
    ) -> Approval:
        approval = await session.get(Approval, approval_id)
        if not approval:
            raise ValueError("approval not found")
        if approval.status != "PENDING":
            return approval

        approval.status = "APPROVED" if approve else "REJECTED"
        approval.decided_by = decided_by
        approval.decided_at = datetime.utcnow()

        await self.audit.record(
            session, company_id=approval.company_id, actor_type="user",
            actor_id=decided_by, action="approval.decide", resource=approval.id,
            meta={"approve": approve},
        )

        if approval.resource_type == "invoice":
            invoice = await session.get(Invoice, approval.resource_id)
            if invoice:
                if approve:
                    await self.invoices.mark_approved_and_send(session, invoice, decided_by=decided_by)
                else:
                    await self.invoices.mark_rejected(session, invoice, decided_by=decided_by)

        return approval
