"""Tool registry — declares danger + RBAC at the tool level.

Guardrails enforced by the orchestrator before any tool runs:
  * caller's role >= tool.min_role
  * financial tools route their effect through Approval (never auto-execute)
  * every tool invocation is recorded in the audit log
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.approvals.service import ApprovalService
from app.services.invoices.service import InvoiceService


# ─── Schemas ─────────────────────────────────────────────────────────────────

class InvoiceLineItem(BaseModel):
    name: str
    qty: float = 1
    price: float
    tax: float = 0


class CreateInvoiceArgs(BaseModel):
    client_name: str = Field(..., description="Client / counterparty name")
    items: list[InvoiceLineItem] = Field(..., description="Line items")
    due_in_days: int = 14
    confirm_high_value: bool = Field(
        False,
        description="Pass True only after the user explicitly re-confirmed an amount over the high-value threshold.",
    )


class ListInvoicesArgs(BaseModel):
    status: str | None = Field(None, description="DRAFT|PENDING_APPROVAL|SENT|PAID|OVERDUE|CANCELLED")
    limit: int = 20


# ─── Base ────────────────────────────────────────────────────────────────────

_ROLE_RANK = {"VIEWER": 0, "MEMBER": 1, "ADMIN": 2, "OWNER": 3}


class ToolDenied(Exception):
    """Raised when a tool invocation fails a guardrail check."""


class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    requires_approval: bool = False
    danger: str = "read"        # "read" | "write" | "financial"
    min_role: str = "MEMBER"    # VIEWER < MEMBER < ADMIN < OWNER

    def authorize(self, *, role: str) -> None:
        if _ROLE_RANK.get(role, -1) < _ROLE_RANK.get(self.min_role, 99):
            raise ToolDenied(f"role {role} cannot invoke tool {self.name} (min: {self.min_role})")

    async def run(self, session: AsyncSession, company_id: str, actor_id: str, args: BaseModel) -> dict[str, Any]:
        raise NotImplementedError

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }


# ─── Tools ───────────────────────────────────────────────────────────────────

class CreateInvoiceTool(Tool):
    name = "create_invoice"
    description = (
        "Create a draft invoice for a named client and request human approval before sending. "
        "Use when the user asks to bill, invoice, or charge a counterparty."
    )
    args_model = CreateInvoiceArgs
    requires_approval = True
    danger = "financial"
    min_role = "MEMBER"

    # Belt-and-suspenders: even though the action is approval-gated downstream,
    # block the LLM from generating eye-watering totals without a typed confirmation.
    HIGH_VALUE_THRESHOLD = 1_000_000  # KZT

    async def run(self, session, company_id, actor_id, args: CreateInvoiceArgs):
        total = sum(it.qty * it.price for it in args.items)
        if total >= self.HIGH_VALUE_THRESHOLD and not args.confirm_high_value:
            return {
                "error": "confirmation_required",
                "danger": "financial",
                "threshold": self.HIGH_VALUE_THRESHOLD,
                "amount": total,
                "message": (
                    f"Amount {total:,.0f} KZT exceeds the high-value threshold. "
                    "Ask the user to confirm explicitly, then re-call with confirm_high_value=true."
                ),
            }
        from app.services.templates.matcher import match_best
        q = f"invoice {args.client_name} " + " ".join(it.name for it in args.items)
        m = await match_best(session, company_id=company_id, kind="invoice", query=q)

        invoices = InvoiceService()
        approvals = ApprovalService()
        invoice = await invoices.create_draft(
            session, company_id=company_id,
            client_name=args.client_name,
            items=[i.model_dump() for i in args.items],
            due_in_days=args.due_in_days,
            actor_type="ai", actor_id=actor_id,
        )
        approval = await approvals.request_invoice_send(session, invoice=invoice, requested_by="ai")
        pdf_url = getattr(invoice, "_ai_render_meta", {}).get("pdf_url")
        return {
            "invoice_id": invoice.id, "number": invoice.number,
            "total": str(invoice.total), "currency": invoice.currency,
            "status": invoice.status, "approval_id": approval.id,
            "danger": "financial",
            "template_id":     m.template.id if m.template else None,
            "template_name":   m.template.name if m.template else None,
            "template_format": m.template.format if m.template else "html",
            "template_reason": m.reason,
            "template_score":  m.score,
            "template_breakdown": m.breakdown,
            "template_matched_terms": m.matched_terms,
            "template_alternatives": [
                {"id": t.id, "name": t.name, "score": s}
                for t, s in (m.alternatives or [])
            ],
            "template_ambiguous": m.ambiguous,
            "pdf_url":  pdf_url,
            "html_url": (f"/api/v1/files/{invoice.pdf_key}" if invoice.pdf_key and not pdf_url else None),
            "needs_review": [
                {"id": t.id, "name": t.name, "kind": t.kind, "status": t.status}
                for t in (m.needs_review or [])
            ],
            "message": f"Draft invoice {invoice.number} created for {args.client_name}. Approval requested.",
        }


class ListInvoicesTool(Tool):
    name = "list_invoices"
    description = "List invoices, optionally filtered by status."
    args_model = ListInvoicesArgs
    danger = "read"
    min_role = "VIEWER"

    async def run(self, session, company_id, actor_id, args: ListInvoicesArgs):
        invoices = await InvoiceService().list(session, company_id)
        if args.status:
            invoices = [i for i in invoices if i.status == args.status]
        invoices = invoices[: args.limit]
        return {"invoices": [
            {"id": i.id, "number": i.number, "total": str(i.total),
             "currency": i.currency, "status": i.status}
            for i in invoices
        ]}


# ─── Registry ────────────────────────────────────────────────────────────────

class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self._by_name = {t.name: t for t in tools}

    def __iter__(self):
        return iter(self._by_name.values())

    def get(self, name: str) -> Tool:
        return self._by_name[name]

    def openai_schema(self) -> list[dict[str, Any]]:
        return [t.openai_schema() for t in self._by_name.values()]

    def manifest(self) -> list[dict[str, Any]]:
        return [{"name": t.name, "description": t.description, "danger": t.danger,
                 "min_role": t.min_role, "requires_approval": t.requires_approval}
                for t in self._by_name.values()]

    @classmethod
    def default(cls) -> "ToolRegistry":
        return cls([CreateInvoiceTool(), ListInvoicesTool()])
