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

from app.core.logging import log
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


class DocumentLineItem(BaseModel):
    name: str = Field(..., description="Item description, e.g. 'разработка CRM'.")
    qty: float = Field(1, description="Quantity. Default 1.")
    price: float | None = Field(
        None,
        description=(
            "Unit price. If absent, computed from total/qty. "
            "Either price OR total must be set."
        ),
    )
    total: float | None = Field(
        None,
        description="Row total (qty * price). If absent, computed from qty * price.",
    )


class GenerateDocumentArgs(BaseModel):
    kind: str = Field(
        ...,
        description=(
            "One of: invoice, act, nakladnaya, contract, trust_letter, "
            "contract_services, contract_supply, act_reconciliation, "
            "hr_order, employment_contract, arbitrary_template. "
            "act_reconciliation = акт сверки взаиморасчётов (debit/credit "
            "ledger between two parties) — NOT 'act' (акт выполненных "
            "работ, a one-off delivery acceptance). contract_services = "
            "договор оказания услуг; contract_supply = договор поставки "
            "(goods). hr_order = short internal приказ о приёме на работу; "
            "employment_contract = full трудовой договор."
        ),
    )
    prompt: str | None = Field(
        None, description="The user's natural-language request, verbatim, for intent fallback.",
    )
    client_name: str | None = Field(None, description="Counterparty name (TOO/ИП/АО ...).")
    total: float | None = Field(None, description="Total amount; if absent, falls back to intent parse.")
    currency: str = Field("KZT", description="ISO currency code; KZT default for Kazakhstan.")
    items: list[DocumentLineItem] | None = Field(
        None,
        description=(
            "Multi-row table items. **REQUIRED** when the user lists more than one "
            "service/product (e.g. 'разработка — 350000\\nдизайн — 120000'). Each "
            "entry becomes ONE row in the document's items table. Do NOT collapse "
            "multiple items into a single item_description string."
        ),
    )
    item_description: str | None = Field(
        None,
        description=(
            "Single-line item description — use ONLY when there is exactly one "
            "service/product. For multiple items use the `items` array."
        ),
    )
    qty: float = 1
    vat_percent: float | None = Field(None, description="VAT %; defaults to company accounting settings.")
    notes: str | None = None
    extra_fields: dict[str, Any] | None = Field(
        None,
        description=(
            "Kind-specific fields not covered above, extracted from the user's "
            "request. Use exactly these key names (all optional, include only "
            "what the user actually gave you):\n"
            "  trust_letter: employee_name, employee_position, employee_iin, "
            "employee_id_doc, valid_until (date), from_name, from_bin (whose "
            "goods to receive)\n"
            "  contract_services / contract_supply: client_bin, client_address, "
            "client_director_name, service_description, delivery_terms, "
            "delivery_address, delivery_date, payment_terms, start_date, "
            "end_date, city\n"
            "  act_reconciliation: client_bin, client_address, period_start, "
            "period_end, opening_balance (number), operations (list of "
            "{date, doc_ref, debit, credit} — debit/credit as plain numbers, "
            "never pre-computed running balances, the app computes those)\n"
            "  hr_order: employee_name, employee_iin, employee_position, "
            "employee_department, hire_date, salary (number), probation_period\n"
            "  employment_contract: employee_name, employee_iin, employee_address, "
            "employee_id_doc, employee_position, employee_department, "
            "work_start_date, contract_term, salary (number), pay_dates, "
            "work_schedule, probation_period, vacation_days, city"
        ),
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _merge_items_into_intent(intent, args) -> None:
    """Resolve the items conflict between the deterministic prompt parser
    and the LLM-supplied args. The parser wins when it found multi-line
    items, because:

      * `parse_line_items` is deterministic — same input always yields the
        same rows — so we can reason about it.
      * Real-world LLMs frequently collapse multi-line item lists into a
        single ``item_description`` + ``total`` (the first amount on the
        page) OR hallucinate extra rows that weren't in the prompt.

    Priority used here:
      1. parser found ≥1 row in the prompt → use those; ignore LLM
         args.items / args.total / args.item_description / args.qty
      2. LLM supplied a valid args.items list → use it
      3. Single-item fallback → args.item_description + (args.total or qty/price)
    """
    parser_items = list(intent.parsed_items or [])
    llm_items = _serialize_items(args.items)

    if parser_items:
        # Trust the parser. LLM's scalar fields would corrupt totals.
        intent.parsed_items = parser_items
        intent.total = sum(float(it.get("total") or 0) for it in parser_items)
        return

    if llm_items:
        intent.parsed_items = llm_items
        intent.total = sum(float(it.get("total") or 0) for it in llm_items)
        return

    # No structured items anywhere — single-row fallback path.
    if args.total is not None:        intent.total = float(args.total)
    if args.item_description:         intent.item_description = args.item_description
    if args.qty is not None:          intent.qty = float(args.qty)


def _serialize_items(items: list[DocumentLineItem] | None) -> list[dict[str, Any]] | None:
    """Normalise LLM-supplied items into the dict shape the renderer expects.

    Each output row has ``name / qty / price / total`` populated, deriving the
    missing scalar from whichever side was provided. Rows that have neither a
    price nor a total are skipped — they're noise (Jinja would render zeros
    in the table) rather than meaningful data.
    """
    if not items:
        return None
    rows: list[dict[str, Any]] = []
    for it in items:
        qty = float(it.qty) if it.qty else 1.0
        price = float(it.price) if it.price is not None else None
        total = float(it.total) if it.total is not None else None
        if price is None and total is None:
            continue
        if total is None:
            total = qty * (price or 0)
        if price is None:
            price = total / qty if qty else total
        rows.append({"name": it.name, "qty": qty, "price": price, "total": total})
    return rows or None


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

    async def run(
        self,
        session: AsyncSession,
        company_id: str,
        actor_id: str,
        args: BaseModel,
        *,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
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

    async def run(self, session, company_id, actor_id, args: CreateInvoiceArgs, *, conversation_id=None):
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

    async def run(self, session, company_id, actor_id, args: ListInvoicesArgs, *, conversation_id=None):
        invoices = await InvoiceService().list(session, company_id)
        if args.status:
            invoices = [i for i in invoices if i.status == args.status]
        invoices = invoices[: args.limit]
        return {"invoices": [
            {"id": i.id, "number": i.number, "total": str(i.total),
             "currency": i.currency, "status": i.status}
            for i in invoices
        ]}


class GetTaxInfoArgs(BaseModel):
    topic: str | None = Field(
        None,
        description=(
            "Optional free-text hint of what the user is asking about "
            "(e.g. 'ОПВ', 'упрощёнка', 'форма 910'), for logging only — "
            "the tool always returns the full structured rate table, you "
            "pick the relevant fields from it."
        ),
    )


class GetTaxInfoTool(Tool):
    name = "get_tax_info"
    description = (
        "READ-ONLY lookup of the structured 2026 Kazakhstan tax-rate knowledge base "
        "(ОПВ/ОПВР/ВОСМС/ООСМС/СО/социальный налог/ИПН rates and bases, спецрежимы "
        "— упрощёнка/самозанятые/ОУР, form 910/200/100 filing deadlines). Call this "
        "whenever the user asks 'какие налоги...', 'когда сдавать...', 'сколько "
        "составляет ставка...', or anything about KZ tax rates, thresholds, or "
        "reporting deadlines. NEVER answer such questions from memory/training data — "
        "always call this tool first and quote ONLY the numbers it returns, since "
        "rates changed materially for 2026 versus prior years. Always include the "
        "returned disclaimer and effective date in your reply."
    )
    args_model = GetTaxInfoArgs
    danger = "read"
    min_role = "VIEWER"

    async def run(self, session, company_id, actor_id, args: GetTaxInfoArgs, *, conversation_id=None):
        from app.services.tax.rates import load_rates, disclaimer
        return {**load_rates(), "disclaimer_full": disclaimer()}


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
        return cls([
            CreateInvoiceTool(), ListInvoicesTool(),
            ProposeDocumentTool(), GenerateDocumentTool(),
            GetTaxInfoTool(),
        ])


# ── propose_document ────────────────────────────────────────────────────────
#
# Read-only "preview" tool. Returns the intent, the matched template (plus
# top-3 alternatives with reliability data), the missing fields the operator
# would need to fill in, and an explicit `requires_confirmation=True` flag.
# Crucially: NO DB writes, NO render, NO storage — calling this is free.
#
# The orchestrator's system prompt instructs the LLM to ALWAYS call this
# first for generation requests, and only proceed to `generate_document`
# after the user explicitly confirms.

class ProposeDocumentArgs(BaseModel):
    kind: str = Field(
        ...,
        description=(
            "One of: invoice, act, nakladnaya, contract, trust_letter, "
            "contract_services, contract_supply, act_reconciliation, "
            "hr_order, employment_contract, arbitrary_template. "
            "act_reconciliation = акт сверки взаиморасчётов (debit/credit "
            "ledger between two parties) — NOT 'act' (акт выполненных "
            "работ, a one-off delivery acceptance). contract_services = "
            "договор оказания услуг; contract_supply = договор поставки "
            "(goods). hr_order = short internal приказ о приёме на работу; "
            "employment_contract = full трудовой договор."
        ),
    )
    prompt: str | None = Field(
        None, description="The user's natural-language request, verbatim.",
    )
    client_name: str | None = None
    total: float | None = None
    currency: str = "KZT"
    items: list[DocumentLineItem] | None = Field(
        None,
        description=(
            "Multi-row table items. **REQUIRED** when the user lists more than one "
            "service/product. Each entry becomes ONE row in the items table. "
            "Do NOT collapse multiple items into a single item_description."
        ),
    )
    item_description: str | None = Field(
        None,
        description=(
            "Single-line description — ONLY for single-item documents. For "
            "multiple items use the `items` array."
        ),
    )
    qty: float = 1
    vat_percent: float | None = None
    notes: str | None = None
    extra_fields: dict[str, Any] | None = Field(
        None,
        description=(
            "Kind-specific fields not covered above, extracted from the user's "
            "request. Use exactly these key names (all optional, include only "
            "what the user actually gave you):\n"
            "  trust_letter: employee_name, employee_position, employee_iin, "
            "employee_id_doc, valid_until (date), from_name, from_bin (whose "
            "goods to receive)\n"
            "  contract_services / contract_supply: client_bin, client_address, "
            "client_director_name, service_description, delivery_terms, "
            "delivery_address, delivery_date, payment_terms, start_date, "
            "end_date, city\n"
            "  act_reconciliation: client_bin, client_address, period_start, "
            "period_end, opening_balance (number), operations (list of "
            "{date, doc_ref, debit, credit} — debit/credit as plain numbers, "
            "never pre-computed running balances, the app computes those)\n"
            "  hr_order: employee_name, employee_iin, employee_position, "
            "employee_department, hire_date, salary (number), probation_period\n"
            "  employment_contract: employee_name, employee_iin, employee_address, "
            "employee_id_doc, employee_position, employee_department, "
            "work_start_date, contract_term, salary (number), pay_dates, "
            "work_schedule, probation_period, vacation_days, city"
        ),
    )


class ProposeDocumentTool(Tool):
    name = "propose_document"
    description = (
        "READ-ONLY preview. Parses the request, picks the best template, and "
        "returns a proposal card the operator can confirm or adjust. NO document "
        "is created. Always call this BEFORE generate_document so the user can "
        "review the chosen template, see top alternatives, edit missing fields, "
        "and explicitly confirm. Use generate_document only after the user has "
        "confirmed in their next message (e.g. 'да', 'подтверждаю', 'создай', "
        "'yes', 'confirm')."
    )
    args_model = ProposeDocumentArgs
    requires_approval = False
    danger = "read"
    min_role = "VIEWER"

    async def run(self, session, company_id, actor_id, args: ProposeDocumentArgs, *, conversation_id=None):
        from app.services.documents.generation.context_builder import build_canonical_context
        from app.services.documents.generation.intent import parse_intent
        from app.services.documents.generation.pipeline import SUPPORTED_KINDS
        from app.services.context.service import load_context
        from app.services.templates.matcher import match_best
        from app.services.templates.reliability import reliability_bonus_map
        from app.services.proposals import create_pending

        kind = (args.kind or "").strip().lower()
        if kind not in SUPPORTED_KINDS:
            return {
                "error": "unsupported_kind",
                "supported": sorted(SUPPORTED_KINDS),
                "message": f"kind={args.kind!r} is not supported.",
            }

        # 1) Parse intent (single source of truth for multi-item etc.).
        intent = await parse_intent(args.prompt or "")
        intent.kind = kind
        if args.client_name: intent.client_name = args.client_name
        if args.currency: intent.currency = args.currency
        if args.vat_percent is not None: intent.vat_percent = float(args.vat_percent)
        _merge_items_into_intent(intent, args)
        log.info("propose.intent_resolved", kind=kind,
                  client=intent.client_name,
                  items_count=len(intent.parsed_items),
                  items_total=intent.total,
                  parsed_from_prompt=bool(intent.parsed_items),
                  llm_items_supplied=bool(args.items))

        # 2) Run matcher to discover template + top alternatives.
        match = await match_best(
            session, company_id=company_id, kind=kind,
            query=intent.raw_text or (intent.client_name or "") + " " + (intent.item_description or ""),
        )

        # 3) Hydrate reliability data for top candidates so the UI can show
        #    "Reliability 95/100" next to each option.
        top_ids: list[str] = []
        if match.template:                top_ids.append(match.template.id)
        for t, _ in (match.alternatives or [])[:3]:
            if t.id not in top_ids:        top_ids.append(t.id)
        reliability = await reliability_bonus_map(
            session, company_id=company_id, template_ids=top_ids,
        )

        def _tpl_dict(t, score):
            r_bonus, op_score = reliability.get(t.id, (0, 70))
            return {
                "id": t.id, "name": t.name, "format": t.format,
                "verified": t.status == "VERIFIED",
                "match_score": score,
                "operational_score": op_score,
                "is_default": t.is_default,
            }

        suggested = _tpl_dict(match.template, match.score) if match.template else None
        alternatives = [_tpl_dict(t, s) for t, s in (match.alternatives or [])[:3]]

        # 4) Build canonical context to show preview values (no render).
        business = await load_context(session, company_id)
        canonical = build_canonical_context(
            business=business, intent=intent,
            document_number="(будет назначен)",
            overrides=args.extra_fields or {},
        )

        # 5) Identify missing-but-recommended fields the operator should fill.
        missing: list[dict[str, str]] = []
        if not intent.client_name:
            missing.append({"field": "client_name",
                             "label": "Клиент / контрагент",
                             "hint": "Например: TOO Sigma"})
        if intent.total is None or intent.total == 0:
            missing.append({"field": "total",
                             "label": "Сумма",
                             "hint": "Например: 450000"})

        items_preview = canonical.get("items") or []

        human_kind = {
            "invoice": "Счёт на оплату",
            "act": "Акт выполненных работ",
            "nakladnaya": "Товарная накладная",
            "contract": "Договор",
            "trust_letter": "Доверенность",
            "contract_services": "Договор оказания услуг",
            "contract_supply": "Договор поставки",
            "act_reconciliation": "Акт сверки взаиморасчётов",
            "hr_order": "Приказ о приёме на работу",
            "employment_contract": "Трудовой договор",
            "arbitrary_template": "Документ",
        }.get(kind, "Документ")

        # Persist a PendingProposal so the web flow has the same gateable
        # state as Telegram. Without this row, GenerateDocumentTool's
        # propose-before-generate gate would reject every confirmation as
        # "proposal_required" — the original web-only bug.
        #
        # Telegram calls this tool directly (deterministic_propose path)
        # WITHOUT conversation_id, and persists its own PendingProposal
        # row downstream with channel="telegram" and the telegram chat_id.
        # To avoid double-rows, we only create the web-channel row when
        # the orchestrator passed a real conversation_id.
        proposal_id: str | None = None
        if conversation_id:
            pending = await create_pending(
                session, company_id=company_id, user_id=actor_id,
                channel="web", chat_id=conversation_id, conversation_id=conversation_id,
                kind=kind,
                payload={
                    "client_name":  intent.client_name,
                    "total":        intent.total,
                    "currency":     intent.currency,
                    "vat_percent":  intent.vat_percent,
                    "item_description": intent.item_description,
                    "items":        list(intent.parsed_items or []),
                    "notes":        args.notes,
                    "prompt":       args.prompt,
                },
                template_id=(match.template.id if match.template else None),
            )
            proposal_id = pending.id
            log.info("proposal_created",
                      proposal_id=pending.id, conversation_id=conversation_id,
                      channel="web", kind=kind, user_id=actor_id,
                      client=intent.client_name, total=intent.total)

        return {
            "type": "document_proposal",
            "requires_confirmation": True,
            "proposal_id": proposal_id,
            "kind": kind,
            "human_kind": human_kind,
            "intent": {
                "client_name":  intent.client_name,
                "total":        intent.total,
                "currency":     intent.currency,
                "vat_percent":  intent.vat_percent,
                "confidence":   round(intent.confidence, 2),
            },
            "items_preview": [
                {"name": it.get("name"), "qty": it.get("qty"),
                 "price": it.get("price"), "total": it.get("total")}
                for it in items_preview
            ],
            "items_count":   len(items_preview),
            "suggested_template": suggested,
            "alternatives":  alternatives,
            "ambiguous":     match.ambiguous,
            "match_reason":  match.reason,
            "missing_fields": missing,
            "preview_context": {
                "company_name":  canonical.get("company_name"),
                "company_bin":   canonical.get("company_bin"),
                "client_name":   canonical.get("client_name"),
                "client_bin":    canonical.get("client_bin"),
                "currency":      canonical.get("currency"),
                "subtotal":      canonical.get("subtotal"),
                "vat":           canonical.get("vat"),
                "vat_percent":   canonical.get("vat_percent"),
                "total":         canonical.get("total"),
            },
            "message": (
                f"Готов подготовить {human_kind.lower()}"
                + (f" для {intent.client_name}" if intent.client_name else "")
                + (f" на сумму {canonical.get('total')} {intent.currency}"
                   if intent.total else "")
                + ". Проверьте параметры и нажмите «Подтвердить» — после этого "
                "документ будет сгенерирован."
            ),
        }


class GenerateDocumentTool(Tool):
    name = "generate_document"
    description = (
        "Generate a REAL populated Kazakhstan business document (DOCX/PDF) from the "
        "company's uploaded template library. Use this for ANY user request to create, "
        "issue, prepare, or render a document — invoice / счёт, акт, накладная, "
        "договор, доверенность, etc. The document is created immediately and is "
        "downloadable right away; an approval is requested in parallel for sending. "
        "Do NOT use create_invoice for non-invoice documents — use this tool instead."
    )
    args_model = GenerateDocumentArgs
    requires_approval = True
    danger = "financial"
    min_role = "MEMBER"

    HIGH_VALUE_THRESHOLD = 1_000_000

    async def run(self, session, company_id, actor_id, args: GenerateDocumentArgs, *, conversation_id=None):
        from app.services.documents.generation import GenerationPipeline, SUPPORTED_KINDS
        from app.services.proposals import (
            find_active, claim_for_generation, mark_completed, ProposalStatus,
        )
        from sqlalchemy import desc, select
        from app.db.models import PendingProposal

        kind = (args.kind or "").strip().lower()
        if kind not in SUPPORTED_KINDS:
            return {
                "error": "unsupported_kind",
                "supported": sorted(SUPPORTED_KINDS),
                "message": f"kind={args.kind!r} is not supported. Pick one of {sorted(SUPPORTED_KINDS)}.",
            }

        # Propose-before-generate gate, with atomic AWAITING → GENERATING
        # claim. Looks up the user's active proposal in this conversation
        # (channel-agnostic: web uses conversation_id as chat_id, telegram
        # uses the telegram chat_id). If the active proposal exists, we
        # atomically claim it so repeated confirmations can't double-fire.
        # If no active proposal exists, we fall back to the legacy
        # 15-minute-window check so a recently-COMPLETED proposal still
        # allows a "create another like this" follow-up.
        active = await find_active(
            session,
            company_id=company_id, user_id=actor_id,
            channel="web", chat_id=conversation_id,
        )
        claimed_proposal = None
        if active is not None:
            log.info("proposal_found",
                      proposal_id=active.id, kind=active.kind,
                      conversation_id=conversation_id, user_id=actor_id)
            claimed_proposal = await claim_for_generation(
                session, proposal_id=active.id, user_id=actor_id,
            )
            if claimed_proposal is None:
                # Lost the race to a concurrent confirmation. Treat as
                # in-flight, not as a hard error — the parallel call will
                # actually produce the document.
                log.info("proposal_claim_lost",
                          proposal_id=active.id, conversation_id=conversation_id)
                return {
                    "error": "proposal_in_flight",
                    "message": (
                        "Документ уже создаётся (параллельное подтверждение). "
                        "Подождите пару секунд."
                    ),
                }
            log.info("proposal_claimed",
                      proposal_id=claimed_proposal.id,
                      conversation_id=conversation_id, user_id=actor_id)

        if claimed_proposal is None:
            # No live AWAITING row — accept if any recently completed
            # proposal of this kind exists for the user (the "create
            # another similar" path).
            from datetime import datetime, timedelta
            recent = await session.scalar(
                select(PendingProposal).where(
                    PendingProposal.company_id == company_id,
                    PendingProposal.user_id == actor_id,
                    PendingProposal.kind == kind,
                    PendingProposal.status.in_(
                        [ProposalStatus.GENERATING, ProposalStatus.COMPLETED],
                    ),
                ).order_by(desc(PendingProposal.created_at)).limit(1),
            )
            within = (
                recent is not None
                and (datetime.utcnow() - recent.created_at) <= timedelta(minutes=15)
            )
            if not within:
                log.warning("proposal_missing", kind=kind,
                              user_id=actor_id, company_id=company_id,
                              conversation_id=conversation_id)
                return {
                    "error": "proposal_required",
                    "message": (
                        "Сначала нужно подготовить предложение по документу. "
                        "Опишите что создать (например: «создай акт для Никиты на 60000»), "
                        "затем подтвердите кнопкой «Подтвердить и создать» или сообщением «да»."
                    ),
                }

        log.info("generation_started",
                  kind=kind, conversation_id=conversation_id, user_id=actor_id,
                  proposal_id=(claimed_proposal.id if claimed_proposal else None))

        # Build a temporary intent so we can apply the parser-wins priority
        # BEFORE handing override values off to the pipeline. This mirrors
        # ProposeDocumentTool.run — divergence between the two would be
        # the exact data-consistency bug we just fixed.
        from app.services.documents.generation.intent import parse_intent
        intent = await parse_intent(args.prompt or "")
        # Snapshot before kind/overrides mutate it below — used only for the
        # `parsed_from_prompt` diagnostic, so we don't re-parse (and re-fire
        # the LLM classifier) a second time just to check this flag.
        parsed_from_prompt = bool(intent.parsed_items)
        intent.kind = kind
        if args.client_name: intent.client_name = args.client_name
        if args.currency: intent.currency = args.currency
        if args.vat_percent is not None: intent.vat_percent = float(args.vat_percent)
        _merge_items_into_intent(intent, args)
        log.info("generate.intent_resolved", kind=kind,
                  client=intent.client_name,
                  items_count=len(intent.parsed_items),
                  items_total=intent.total,
                  parsed_from_prompt=parsed_from_prompt,
                  llm_items_supplied=bool(args.items))

        overrides = {
            "client_name":      intent.client_name,
            "total":            intent.total,
            "currency":         intent.currency,
            "item_description": intent.item_description if not intent.parsed_items else None,
            "qty":              intent.qty if not intent.parsed_items else None,
            "vat_percent":      intent.vat_percent,
            "notes":            args.notes,
            **(args.extra_fields or {}),
            # `parsed_items` is the canonical list of dicts after merge.
            "items":            list(intent.parsed_items) if intent.parsed_items else None,
        }
        overrides = {k: v for k, v in overrides.items() if v not in (None, "")}

        pipeline = GenerationPipeline()
        try:
            result = await pipeline.generate(
                session, company_id=company_id, actor_id=actor_id,
                kind=kind, prompt=args.prompt, overrides=overrides,
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("generation_failed",
                            kind=kind, conversation_id=conversation_id,
                            user_id=actor_id, error=str(exc),
                            proposal_id=(claimed_proposal.id if claimed_proposal else None))
            # Surface the failure on the claimed proposal so the user isn't
            # left with a stale "GENERATING" row that no UI affordance can
            # recover from.
            if claimed_proposal is not None:
                from app.services.proposals.store import mark_cancelled
                await mark_cancelled(
                    session, proposal_id=claimed_proposal.id, user_id=actor_id,
                )
            raise

        if claimed_proposal is not None:
            await mark_completed(
                session, proposal_id=claimed_proposal.id,
                document_id=result.document_id,
            )
        log.info("generation_finished",
                  kind=kind, conversation_id=conversation_id, user_id=actor_id,
                  proposal_id=(claimed_proposal.id if claimed_proposal else None),
                  document_id=result.document_id, number=result.document_number)

        human_kind = {
            "invoice": "Счёт", "act": "Акт", "nakladnaya": "Накладная",
            "contract": "Договор", "trust_letter": "Доверенность",
            "contract_services": "Договор оказания услуг",
            "contract_supply": "Договор поставки",
            "act_reconciliation": "Акт сверки взаиморасчётов",
            "hr_order": "Приказ о приёме на работу",
            "employment_contract": "Трудовой договор",
            "arbitrary_template": "Документ",
        }.get(kind, "Документ")

        q = result.quality or {}
        approval_label = {
            "BLOCKED": "blocked", "PENDING": "pending", "APPROVED": "approved",
        }.get(result.approval_status or "", (result.approval_status or "").lower())
        status_icon = {"ok": "✅", "warning": "⚠️", "blocked": "⛔"}.get(q.get("status", ""), "")

        fallback_warning = None
        if result.fallback_used:
            fallback_warning = {
                "severity": "warning",
                "title": "Original template could not be rendered — fallback layout used",
                "reason": result.fallback_reason,
                "engine": result.fallback_engine,
            }

        # Operational card — the UI renders this directly; do not concatenate
        # all signal into the message field.
        card = {
            "type": "generated_document",
            "kind": result.kind,
            "title": f"{human_kind} {result.document_number}",
            "subtitle": (f"Клиент: {args.client_name}" if args.client_name else None),
            "template": {
                "id":                result.template_id,
                "name":              result.template_name or "Built-in HTML fallback",
                "format":            result.template_format,
                "score":             result.match_score,
                "reason":            result.match_reason,
                "verified":          result.template_verified,
                "operational_score": result.template_operational_score,
            },
            "files": {
                "pdf":  {"ready": bool(result.pdf_url),  "url": result.pdf_url},
                "docx": {"ready": bool(result.docx_url) and (result.template_format != "html"),
                          "url": result.docx_url},
                "preview_url": result.primary_url,
            },
            "quality": {
                "score":   q.get("score"),
                "status":  q.get("status"),
                "blocking": q.get("blocking", False),
                "issues":  q.get("issues", []),
            },
            "approval": {
                "id":      result.approval_id,
                "status":  approval_label,
                "blocked": result.approval_status == "BLOCKED",
            },
            "adaptation": {
                "applied":          result.adaptation_applied,
                "anchors_injected": result.adaptation_anchors_injected,
            },
            "fallback": {
                "used":    result.fallback_used,
                "reason":  result.fallback_reason,
                "engine":  result.fallback_engine,
                "warning": fallback_warning,
            },
            "render": {"duration_ms": result.render_duration_ms},
            "diagnostics_count": len(result.diagnostics or []),
        }

        # Operator-facing summary. One short sentence — the structured card
        # carries the technical detail. Avoid debug-style "score=", "anchor(s)".
        client_phrase = f" для {args.client_name}" if args.client_name else ""
        if result.approval_status == "BLOCKED":
            message = (
                f"⛔ {human_kind} {result.document_number}{client_phrase} подготовлен, "
                "но не прошёл проверку качества. Документ доступен для просмотра — "
                "ниже видно, что нужно исправить."
            )
        elif result.fallback_used:
            message = (
                f"⚠️ {human_kind} {result.document_number}{client_phrase} готов "
                "(использован встроенный fallback-шаблон — оригинальный шаблон не подошёл). "
                "PDF можно скачать."
            )
        elif result.pdf_url:
            message = (
                f"Готово. {human_kind} {result.document_number}{client_phrase}. "
                f"PDF готов к отправке."
            )
        else:
            message = (
                f"{human_kind} {result.document_number}{client_phrase} сгенерирован, "
                "PDF не собран — см. диагностику в карточке."
            )

        return {
            "card":             card,
            "document_id":      result.document_id,
            "number":           result.document_number,
            "pdf_url":          result.pdf_url,
            "docx_url":         result.docx_url,
            "primary_url":      result.primary_url,
            "approval_id":      result.approval_id,
            "approval_status":  result.approval_status,
            "quality_score":    q.get("score"),
            "quality_status":   q.get("status"),
            "fallback_used":    result.fallback_used,
            "fallback_reason":  result.fallback_reason,
            "fallback_engine":  result.fallback_engine,
            "adaptation_applied": result.adaptation_applied,
            "adaptation_anchors_injected": result.adaptation_anchors_injected,
            "warnings":         result.warnings,
            "danger":           "financial",
            "message":          message,
        }
