"""Declarative per-kind required-field expectations for render QA.

Add a new document kind by adding one entry to ``KIND_REQUIRED_FIELDS`` —
``check_render_quality()`` in ``quality.py`` never needs an if/elif branch
for it. Two check flavors:
  - "scalar": the canonical context key must be a real, non-empty value.
  - "list":   the canonical context key must be a list with >=1 entry.

``KINDS_WITH_TOTAL_ITEMS_CHECK`` gates the invoice-shaped checks (grand
total present, sum-of-items matches total, items-table row count) — only
kinds that actually render a generic {{items}} table with a single grand
total belong here. A kind left out gets none of those three checks, so a
document like an акт сверки (which has a running balance and an
``operations`` table instead) doesn't get flagged for "missing total" —
that used to hard-block every act_reconciliation/hr_order/employment_
contract/trust_letter generation regardless of whether it actually
rendered correctly.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequiredField:
    key: str
    label: str
    check: str = "scalar"     # "scalar" | "list"
    severity: str = "error"
    weight: int = 20


# Checked for every kind, regardless of document shape.
UNIVERSAL_REQUIRED: tuple[RequiredField, ...] = (
    RequiredField("company_name", "Company name"),
    RequiredField("document_number", "Document number"),
)

# Kind-specific requirements, on top of the universal set above.
KIND_REQUIRED_FIELDS: dict[str, tuple[RequiredField, ...]] = {
    "invoice": (
        RequiredField("client_name", "Client name"),
    ),
    "act": (
        RequiredField("client_name", "Client name"),
    ),
    "nakladnaya": (
        RequiredField("client_name", "Client name"),
    ),
    "contract": (
        RequiredField("client_name", "Client name"),
    ),
    "contract_services": (
        RequiredField("client_name", "Client name"),
        RequiredField("service_description", "Service description"),
    ),
    "contract_supply": (
        RequiredField("client_name", "Client name"),
    ),
    "trust_letter": (
        RequiredField("employee_name", "Доверенное лицо"),
        RequiredField("valid_until", "Срок действия доверенности"),
    ),
    "act_reconciliation": (
        RequiredField("client_name", "Контрагент"),
        RequiredField("operations", "Операции (таблица)", check="list"),
    ),
    "hr_order": (
        RequiredField("employee_name", "Сотрудник"),
        RequiredField("employee_position", "Должность"),
        RequiredField("hire_date", "Дата приёма"),
    ),
    "employment_contract": (
        RequiredField("employee_name", "Работник"),
        RequiredField("employee_position", "Должность"),
        RequiredField("salary", "Оклад"),
    ),
}

# Kinds not declared above (arbitrary_template, any future kind someone
# forgets to register here) fall back to this minimal set rather than
# silently checking nothing.
DEFAULT_REQUIRED_FIELDS: tuple[RequiredField, ...] = (
    RequiredField("client_name", "Client name"),
)

# Only these kinds render a generic repeating {{items}} table with a single
# grand total — the total-present / items-non-empty / totals-match /
# items-row-count checks only make sense for them.
KINDS_WITH_TOTAL_ITEMS_CHECK: frozenset[str] = frozenset({
    "act", "invoice", "nakladnaya", "contract_supply",
})


def required_fields_for(kind: str) -> tuple[RequiredField, ...]:
    return UNIVERSAL_REQUIRED + KIND_REQUIRED_FIELDS.get(kind, DEFAULT_REQUIRED_FIELDS)
