"""Canonical placeholder registry — single source of truth.

The renderer expects a `BusinessContext`-shaped context dict. Every template
field (DOCX bookmark, XLSX cell, HTML token) maps to one of these canonical
keys. Synonyms cover RU/KZ/EN accounting vocabulary.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalField:
    key: str         # placeholder name, e.g. "company_name"
    group: str       # company|client|invoice|tables|signatures|misc
    label: str       # human label
    sample: str      # demo value used in preview render


CANONICAL: dict[str, CanonicalField] = {
    f.key: f for f in [
        # Company
        CanonicalField("company_name",     "company", "Company name",        "TOO Demo"),
        CanonicalField("company_bin",      "company", "Company BIN/Tax ID",  "123456789012"),
        CanonicalField("company_address",  "company", "Company address",     "Almaty, Abay 100"),
        CanonicalField("company_bank",     "company", "Company bank",        "Kaspi Bank · KZ12 ..."),
        CanonicalField("director_name",    "company", "Director",            "А. Иванов"),
        CanonicalField("accountant_name",  "company", "Accountant",          "М. Петрова"),
        # Client
        CanonicalField("client_name",      "client",  "Client name",         "TOO ABC"),
        CanonicalField("client_bin",       "client",  "Client BIN",          "987654321098"),
        CanonicalField("client_address",   "client",  "Client address",      "Astana, Mangilik El 50"),
        CanonicalField("client_phone",     "client",  "Client phone",        "+7 701 000 0001"),
        # Invoice
        CanonicalField("invoice_number",   "invoice", "Invoice number",      "INV-2026-0001"),
        CanonicalField("invoice_date",     "invoice", "Issue date",          "2026-05-16"),
        CanonicalField("due_date",         "invoice", "Due date",            "2026-05-30"),
        CanonicalField("currency",         "invoice", "Currency",            "KZT"),
        CanonicalField("subtotal",         "invoice", "Subtotal",            "450000"),
        CanonicalField("vat",              "invoice", "VAT amount",          "54000"),
        CanonicalField("vat_percent",      "invoice", "VAT percent",         "12"),
        CanonicalField("total",            "invoice", "Total",               "504000"),
        # Tables
        CanonicalField("items",            "tables",  "Line items (repeating)", ""),
        # Signatures
        CanonicalField("signature_block",  "signatures", "Signature block",  ""),
    ]
}

GROUP_ORDER = ["company", "client", "invoice", "tables", "signatures", "misc"]

# Synonyms: lowercased source-label → canonical key. Order matters for ambiguity.
SYNONYMS: list[tuple[str, str, float]] = [
    # (regex/substring, canonical_key, confidence)
    # Company side
    ("поставщик",            "company_name",    0.95),
    ("исполнитель",          "company_name",    0.85),
    ("организация",          "company_name",    0.75),
    ("продавец",             "company_name",    0.90),
    ("наша организация",     "company_name",    0.95),
    ("supplier",             "company_name",    0.85),
    ("seller",               "company_name",    0.85),

    ("бин поставщика",       "company_bin",     0.99),
    ("бин продавца",         "company_bin",     0.99),
    ("бин/иин поставщика",   "company_bin",     0.99),

    ("адрес поставщика",     "company_address", 0.95),
    ("юридический адрес",    "company_address", 0.85),

    ("банковские реквизиты", "company_bank",    0.95),
    ("реквизиты банка",      "company_bank",    0.95),
    ("р/с",                  "company_bank",    0.80),
    ("iban",                 "company_bank",    0.85),

    ("директор",             "director_name",   0.90),
    ("руководитель",         "director_name",   0.85),
    ("director",             "director_name",   0.90),

    ("главный бухгалтер",    "accountant_name", 0.95),
    ("бухгалтер",            "accountant_name", 0.85),
    ("accountant",           "accountant_name", 0.90),

    # Client side
    ("заказчик",             "client_name",     0.95),
    ("покупатель",           "client_name",     0.90),
    ("получатель",           "client_name",     0.80),
    ("контрагент",           "client_name",     0.80),
    ("client",               "client_name",     0.85),
    ("buyer",                "client_name",     0.85),

    ("бин заказчика",        "client_bin",      0.99),
    ("бин покупателя",       "client_bin",      0.99),
    ("бин клиента",          "client_bin",      0.99),
    ("бин",                  "client_bin",      0.60),     # ambiguous — low conf

    ("адрес заказчика",      "client_address",  0.95),
    ("адрес покупателя",     "client_address",  0.95),

    # Invoice fields
    ("номер счета",          "invoice_number",  0.97),
    ("счет №",               "invoice_number",  0.97),
    ("счет на оплату №",     "invoice_number",  0.97),
    ("invoice number",       "invoice_number",  0.95),
    ("invoice no",           "invoice_number",  0.95),
    ("№",                    "invoice_number",  0.55),     # ambiguous

    ("дата счета",           "invoice_date",    0.97),
    ("дата выставления",     "invoice_date",    0.95),
    ("дата документа",       "invoice_date",    0.85),
    ("issue date",           "invoice_date",    0.95),
    ("дата",                 "invoice_date",    0.55),

    ("срок оплаты",          "due_date",        0.95),
    ("оплатить до",          "due_date",        0.95),
    ("due date",             "due_date",        0.95),

    ("валюта",               "currency",        0.95),
    ("currency",             "currency",        0.95),

    ("сумма без ндс",        "subtotal",        0.97),
    ("без ндс",              "subtotal",        0.85),
    ("итого без ндс",        "subtotal",        0.95),
    ("subtotal",             "subtotal",        0.95),

    ("ндс 12",               "vat",             0.95),
    ("ндс",                  "vat",             0.85),
    ("vat",                  "vat",             0.92),
    ("ставка ндс",           "vat_percent",     0.92),

    ("итого к оплате",       "total",           0.98),
    ("всего к оплате",       "total",           0.97),
    ("итого с ндс",          "total",           0.97),
    ("итого",                "total",           0.80),
    ("всего",                "total",           0.75),
    ("total",                "total",           0.95),
    ("amount due",           "total",           0.95),

    # Tables — special handling, see analyzer
    ("товары и услуги",      "items",           0.95),
    ("наименование",         "items",           0.70),
    ("услуги",               "items",           0.65),
    ("items",                "items",           0.90),
]


def suggest(label: str) -> tuple[str, float] | None:
    """Best canonical match for a free-text label. Returns (key, confidence)
    or None when no synonym scores above threshold."""
    l = (label or "").strip().lower()
    if not l:
        return None
    # Exact placeholder hit ("{{company_name}}" → "company_name")
    cleaned = l.strip("{} ").replace(" ", "_")
    if cleaned in CANONICAL:
        return (cleaned, 1.0)
    best: tuple[str, float] | None = None
    for pattern, key, conf in SYNONYMS:
        if pattern in l:
            if best is None or conf > best[1]:
                best = (key, conf)
    return best
