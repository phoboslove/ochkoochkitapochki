"""Canonical context builder — Phase 2.

Merges BusinessContext (company-side) + IntentSpec (per-request) into the
flat canonical dict the template renderer consumes. Exposes both flat and
nested forms so templates can use either ``{{company_name}}`` or
``{{company.name}}``.

This is the single place where natural-language → renderable-context lives.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.services.context.schema import BusinessContext
from app.services.documents.generation.intent import IntentSpec


def _money(v: float | Decimal) -> str:
    return f"{Decimal(str(v)):,.2f}".replace(",", " ")


def build_canonical_context(
    *,
    business: BusinessContext,
    intent: IntentSpec,
    document_number: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a dict keyed by canonical placeholder names + nested aliases.

    Caller MUST provide a stable ``document_number`` (e.g. ACT-2026-0042).
    ``overrides`` (if any) win — they're how the AI passes structured args.
    """
    c = business.company
    a = business.accounting
    bank = c.bank
    items = intent.line_items()
    overrides = overrides or {}

    subtotal = Decimal(str(intent.total or 0))
    vat_rate = (intent.vat_percent if intent.vat_percent is not None
                else (a.vat_percent if a.vat_enabled else 0)) or 0
    vat_amount = (subtotal * Decimal(str(vat_rate)) / Decimal("100")).quantize(Decimal("0.01"))
    total = subtotal + vat_amount

    issue = intent.issue_date or date.today()
    due = issue + timedelta(days=a.due_in_days_default)

    flat: dict[str, Any] = {
        # Company
        "company_name":     c.name,
        "company_bin":      c.bin or "—",
        "company_address":  c.address or "",
        "company_bank":     " · ".join(filter(None, [bank.bank_name, bank.iban])) or "",
        "company_phone":    c.phone or "",
        "company_email":    str(c.email) if c.email else "",
        "director_name":    c.director_name or "",
        "accountant_name":  c.accountant_name or "",

        # Client
        "client_name":      overrides.get("client_name") or intent.client_name or "—",
        "client_bin":       overrides.get("client_bin") or "—",
        "client_address":   overrides.get("client_address") or "",
        "client_phone":     overrides.get("client_phone") or "",

        # Counterparty — second party on multi-sided documents (Telegram
        # users routinely send "Клиент X / Контрагент Y" for two-party
        # acts). Templates that don't reference it just ignore the field.
        "counterparty_name": overrides.get("counterparty_name") or
                              getattr(intent, "counterparty_name", None) or "",

        # Document identity
        "invoice_number":   document_number,
        "document_number":  document_number,
        "invoice_date":     issue.isoformat(),
        "document_date":    issue.isoformat(),
        "due_date":         due.isoformat(),
        "currency":         intent.currency or a.currency_default,

        # Money
        "subtotal":         _money(subtotal),
        "subtotal_raw":     float(subtotal),
        "vat":              _money(vat_amount),
        "vat_raw":          float(vat_amount),
        "vat_percent":      int(vat_rate) if vat_rate else "",
        "total":            _money(total),
        "total_raw":        float(total),
        "amount_words":     _amount_in_words_kzt(total),

        # Tables
        "items":            [
            {**it,
             "price_fmt": _money(it["price"]),
             "total_fmt": _money(it["total"]),
             "idx": idx + 1}
            for idx, it in enumerate(items)
        ],
        "items_count":      len(items),

        # Signatures / misc
        "signature_block":  "",
        "notes":            overrides.get("notes") or "",
    }
    # Pull in any explicit canonical overrides last.
    for k, v in (overrides or {}).items():
        if k in flat and v not in (None, ""):
            flat[k] = v

    # Nested aliases.
    nested = {
        "company":  {"name": flat["company_name"], "bin": flat["company_bin"],
                      "address": flat["company_address"], "bank": flat["company_bank"],
                      "phone": flat["company_phone"], "email": flat["company_email"],
                      "director": flat["director_name"], "accountant": flat["accountant_name"]},
        "client":   {"name": flat["client_name"], "bin": flat["client_bin"],
                      "address": flat["client_address"], "phone": flat["client_phone"]},
        "invoice":  {"number": flat["invoice_number"], "date": flat["invoice_date"],
                      "due_date": flat["due_date"], "currency": flat["currency"],
                      "subtotal": flat["subtotal"], "vat": flat["vat"],
                      "total": flat["total"]},
        "document": {"number": flat["document_number"], "date": flat["document_date"],
                      "total": flat["total"], "currency": flat["currency"]},
    }
    return {**flat, **nested}


# ── Tiny KZT amount-in-words (Russian) ──────────────────────────────────────
#
# Production should swap in num2words; this fallback keeps the slice runnable
# even when no extra dependency is available.

_ONES = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_TEENS = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
           "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
          "семьдесят", "восемьдесят", "девяносто"]


def _amount_in_words_kzt(total: Decimal | float) -> str:
    """Shallow stub — outputs `<digits> тенге` when num2words isn't available."""
    try:
        from num2words import num2words  # type: ignore
        whole = int(Decimal(str(total)))
        cents = int((Decimal(str(total)) - whole) * 100)
        return f"{num2words(whole, lang='ru')} тенге {cents:02d} тиын"
    except Exception:  # noqa: BLE001
        return f"{_money(total)} тенге"
