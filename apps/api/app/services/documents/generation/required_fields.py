"""Declarative per-kind field schema — the single source of truth for what
fields each document kind has, their human labels, and where each one comes
from (company profile / reference-data lookup / system-generated / must be
asked in chat).

Originally this module only carried the quality-gate's required-field list
(``RequiredField`` / ``KIND_REQUIRED_FIELDS`` / ``required_fields_for()``).
It's now extended with a richer ``FieldSpec`` / ``DOCUMENT_SCHEMAS`` that
describe every field per kind (required or not) plus its ``source`` — this
is what lets the AI proposal card, missing-fields logic, and reference-data
autofill all agree on one picture instead of each hardcoding their own
(mostly commercial-shaped) idea of what a document needs.

``KIND_REQUIRED_FIELDS``/``UNIVERSAL_REQUIRED``/``required_fields_for()``
keep their exact current values and signature — they are derived from
``DOCUMENT_SCHEMAS`` below by filtering ``required=True``, so
``quality.py``'s ``check_render_quality()`` needs no changes at all and its
behavior is unchanged. Adding a new *optional* field to a kind's schema
(the common case — most of the fields below are optional) never affects
the quality gate; only flipping a field to ``required=True`` would, so treat
that as a deliberate, separate decision, not a side effect of documenting
a field's existence.

Line-items and their money totals (subtotal/vat/total/amount_words) are
deliberately NOT represented as ``FieldSpec`` entries here — they're already
correctly handled by the existing ``KINDS_WITH_TOTAL_ITEMS_CHECK`` gate
below (grand-total present, sum-of-items matches, items-table row count).
``DocumentSchema.line_items_shape`` just tells a consumer whether this kind
has an items table at all, and if so whether its rows are goods-shaped
(with ТН ВЭД code / артикул) or services-shaped (no such columns) — the
actual presence/correctness check stays exactly where it already lived.
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


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    # "company" | "counterparty" | "employee" | "system" | "user_input"
    source: str
    required: bool = False
    check: str = "scalar"     # "scalar" | "list"
    example: str | None = None
    # Shown when source == "user_input" and the value is missing — what to
    # ask the operator for, instead of a bare "field X is missing".
    ask_hint: str | None = None


@dataclass(frozen=True)
class DocumentSchema:
    kind: str
    human_label: str
    fields: tuple[FieldSpec, ...]
    # "goods" (ед./кол-во/цена/сумма/НДС/ТН ВЭД/артикул) | "services"
    # (same minus ТН ВЭД/артикул) | None (no items table at all).
    line_items_shape: str | None = None


# ─── Shared field groups ────────────────────────────────────────────────────
#
# Reused across every kind's DOCUMENT_SCHEMAS entry below rather than
# repeated inline — one place to add a company/counterparty/employee field
# that every kind should be able to autofill.

_COMPANY_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("company_name", "Наименование компании", source="company", required=True),
    FieldSpec("company_short_name", "Краткое наименование", source="company"),
    FieldSpec("company_bin", "БИН/ИИН компании", source="company"),
    FieldSpec("company_legal_address", "Юридический адрес", source="company"),
    FieldSpec("company_actual_address", "Фактический адрес", source="company"),
    FieldSpec("company_phone", "Телефон компании", source="company"),
    FieldSpec("company_email", "Email компании", source="company"),
    FieldSpec("company_bank_name", "Банк", source="company"),
    FieldSpec("company_bank_bik", "БИК банка", source="company"),
    FieldSpec("company_bank_iik", "ИИК", source="company"),
    FieldSpec("company_bank_kbe", "Кбе", source="company"),
    FieldSpec("company_vat_status", "Статус плательщика НДС", source="company"),
    FieldSpec("company_oked", "ОКЭД", source="company"),
    FieldSpec("director_name", "ФИО директора", source="company"),
    FieldSpec("director_basis", "Основание полномочий директора", source="company",
              example="Устав / доверенность №..."),
    FieldSpec("accountant_name", "ФИО главного бухгалтера", source="company"),
    FieldSpec("city", "Город составления", source="company"),
    FieldSpec("currency", "Валюта", source="company"),
)

_SYSTEM_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("document_number", "Номер документа", source="system", required=True),
    FieldSpec("document_date", "Дата документа", source="system"),
)

# Contragent/counterparty — resolved via fuzzy-match against the Client
# table (see reference_data.matcher, added in a later block); autofilled
# when matched, created with what's known when not.
_COUNTERPARTY_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("client_name", "Клиент / контрагент", source="counterparty", required=True,
              ask_hint="Например: TOO Sigma"),
    FieldSpec("client_bin", "БИН/ИИН контрагента", source="counterparty"),
    FieldSpec("client_address", "Адрес контрагента", source="counterparty"),
    FieldSpec("client_phone", "Телефон контрагента", source="counterparty"),
    FieldSpec("client_signatory_name", "ФИО подписанта контрагента", source="counterparty"),
    FieldSpec("client_signatory_basis", "Основание полномочий подписанта", source="counterparty"),
    FieldSpec("client_bank_name", "Банк контрагента", source="counterparty"),
    FieldSpec("client_bank_bik", "БИК банка контрагента", source="counterparty"),
    FieldSpec("client_bank_iik", "ИИК контрагента", source="counterparty"),
    FieldSpec("client_bank_kbe", "Кбе контрагента", source="counterparty"),
    FieldSpec("client_vat_status", "Статус плательщика НДС контрагента", source="counterparty"),
)

# Employee — resolved the same way against the Employee table (a new
# entity, added alongside the reference-data resolver). hr_order and
# employment_contract are the two kinds that *create/update* this record
# rather than merely read it — see their schemas below.
_EMPLOYEE_LOOKUP_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("employee_name", "Сотрудник", source="employee", required=True),
    FieldSpec("employee_position", "Должность", source="employee"),
    FieldSpec("employee_iin", "ИИН сотрудника", source="employee"),
    FieldSpec("employee_id_doc", "Удостоверение личности", source="employee"),
)

# Base-contract reference ("по договору №... от...") — optional on any kind
# that can point back at a previously signed contract. The system cannot
# know this; it's either given by the operator or left blank.
_BASE_CONTRACT_REF_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("base_contract_number", "Номер договора-основания", source="user_input"),
    FieldSpec("base_contract_date", "Дата договора-основания", source="user_input"),
)

_CONTRACT_TERMS_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("contract_term", "Срок действия договора", source="user_input"),
    FieldSpec("payment_terms", "Порядок и сроки оплаты", source="user_input"),
    FieldSpec("prepayment", "Предоплата", source="user_input"),
    FieldSpec("penalties", "Пени/штрафы", source="user_input"),
)


def _kind_fields(*groups: tuple[FieldSpec, ...]) -> tuple[FieldSpec, ...]:
    out: list[FieldSpec] = []
    for g in groups:
        out.extend(g)
    return tuple(out)


# ─── Per-kind schemas ───────────────────────────────────────────────────────

DOCUMENT_SCHEMAS: dict[str, DocumentSchema] = {
    "invoice": DocumentSchema(
        kind="invoice", human_label="Счёт на оплату",
        line_items_shape="goods",
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS, _COUNTERPARTY_FIELDS,
            _BASE_CONTRACT_REF_FIELDS,
            (FieldSpec("knp_code", "КНП", source="system"),),
        ),
    ),
    "act": DocumentSchema(
        kind="act", human_label="Акт выполненных работ",
        line_items_shape="services",
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS, _COUNTERPARTY_FIELDS,
            _BASE_CONTRACT_REF_FIELDS,
        ),
    ),
    "nakladnaya": DocumentSchema(
        kind="nakladnaya", human_label="Товарная накладная",
        line_items_shape="goods",
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS, _COUNTERPARTY_FIELDS,
            _BASE_CONTRACT_REF_FIELDS,
        ),
    ),
    "contract": DocumentSchema(
        kind="contract", human_label="Договор",
        line_items_shape=None,
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS, _COUNTERPARTY_FIELDS,
            _CONTRACT_TERMS_FIELDS,
        ),
    ),
    "contract_services": DocumentSchema(
        kind="contract_services", human_label="Договор оказания услуг",
        line_items_shape="services",
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS, _COUNTERPARTY_FIELDS,
            _CONTRACT_TERMS_FIELDS,
            (
                FieldSpec("service_description", "Описание услуг", source="user_input",
                          required=True, ask_hint="Что именно нужно сделать?"),
                FieldSpec("start_date", "Дата начала", source="user_input"),
                FieldSpec("end_date", "Дата окончания", source="user_input"),
            ),
        ),
    ),
    "contract_supply": DocumentSchema(
        kind="contract_supply", human_label="Договор поставки",
        line_items_shape="goods",
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS, _COUNTERPARTY_FIELDS,
            _CONTRACT_TERMS_FIELDS,
            (
                FieldSpec("delivery_terms", "Условия поставки", source="user_input"),
                FieldSpec("delivery_address", "Место поставки", source="user_input"),
                FieldSpec("delivery_date", "Срок поставки", source="user_input"),
            ),
        ),
    ),
    "trust_letter": DocumentSchema(
        kind="trust_letter", human_label="Доверенность",
        line_items_shape=None,
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS,
            (
                FieldSpec("employee_name", "Доверенное лицо", source="employee", required=True),
                FieldSpec("employee_position", "Должность доверенного лица", source="employee"),
                FieldSpec("employee_iin", "ИИН доверенного лица", source="employee"),
                FieldSpec("employee_id_doc", "Удостоверение личности", source="employee"),
                FieldSpec("valid_until", "Срок действия доверенности", source="user_input",
                          required=True, ask_hint="До какой даты действует доверенность?"),
                FieldSpec("from_name", "Наименование (чьи товары получать)", source="counterparty"),
                FieldSpec("from_bin", "БИН (чьи товары получать)", source="counterparty"),
            ),
        ),
    ),
    "act_reconciliation": DocumentSchema(
        kind="act_reconciliation", human_label="Акт сверки взаиморасчётов",
        line_items_shape=None,
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS,
            (
                FieldSpec("client_name", "Контрагент", source="counterparty", required=True),
                FieldSpec("client_bin", "БИН/ИИН контрагента", source="counterparty"),
                FieldSpec("client_address", "Адрес контрагента", source="counterparty"),
                FieldSpec("period_start", "Начало периода сверки", source="user_input"),
                FieldSpec("period_end", "Конец периода сверки", source="user_input"),
                FieldSpec("opening_balance", "Начальное сальдо", source="user_input"),
                FieldSpec("operations", "Операции (таблица)", source="user_input",
                          required=True, check="list",
                          ask_hint="Список операций: дата, документ, дебет/кредит"),
                FieldSpec("closing_balance", "Конечное сальдо", source="system"),
            ),
        ),
    ),
    # hr_order / employment_contract are the two "creating" kinds: the
    # employment terms below (position/department/hire_date/salary/...)
    # are what the operator is establishing right now, not something to
    # read off an existing Employee row — after confirmation they're what
    # gets written into the Employee record. employee_iin/address/id_doc
    # come FROM that record when the person already exists (a re-hire, or
    # a later amendment), so they stay source="employee" — the resolver
    # only fills them in if a match is found, it never blocks on them.
    "hr_order": DocumentSchema(
        kind="hr_order", human_label="Приказ о приёме на работу",
        line_items_shape=None,
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS,
            (
                FieldSpec("employee_name", "Сотрудник", source="user_input", required=True,
                          ask_hint="ФИО принимаемого сотрудника"),
                FieldSpec("employee_position", "Должность", source="user_input", required=True),
                FieldSpec("employee_department", "Подразделение", source="user_input"),
                FieldSpec("hire_date", "Дата приёма", source="user_input", required=True),
                FieldSpec("salary", "Оклад", source="user_input"),
                FieldSpec("probation_period", "Испытательный срок", source="user_input"),
                FieldSpec("employee_iin", "ИИН сотрудника", source="employee"),
                FieldSpec("employee_address", "Адрес сотрудника", source="employee"),
                FieldSpec("employee_id_doc", "Удостоверение личности", source="employee"),
            ),
        ),
    ),
    "employment_contract": DocumentSchema(
        kind="employment_contract", human_label="Трудовой договор",
        line_items_shape=None,
        fields=_kind_fields(
            _COMPANY_FIELDS, _SYSTEM_FIELDS,
            (
                FieldSpec("employee_name", "Работник", source="user_input", required=True,
                          ask_hint="ФИО работника"),
                FieldSpec("employee_position", "Должность", source="user_input", required=True),
                FieldSpec("employee_department", "Подразделение", source="user_input"),
                FieldSpec("hire_date", "Дата приёма", source="user_input"),
                FieldSpec("salary", "Оклад", source="user_input", required=True),
                FieldSpec("probation_period", "Испытательный срок", source="user_input"),
                FieldSpec("work_schedule", "График работы", source="user_input"),
                FieldSpec("vacation_days", "Дни отпуска", source="user_input"),
                FieldSpec("pay_dates", "Даты выплаты зарплаты", source="user_input"),
                FieldSpec("contract_term", "Срок действия договора", source="user_input"),
                FieldSpec("employee_iin", "ИИН работника", source="employee"),
                FieldSpec("employee_address", "Адрес работника", source="employee"),
                FieldSpec("employee_id_doc", "Удостоверение личности", source="employee"),
            ),
        ),
    ),
    "arbitrary_template": DocumentSchema(
        kind="arbitrary_template", human_label="Документ",
        line_items_shape=None,
        fields=_kind_fields(_COMPANY_FIELDS, _SYSTEM_FIELDS),
    ),
}


def human_kind_for(kind: str) -> str:
    schema = DOCUMENT_SCHEMAS.get(kind)
    return schema.human_label if schema else "Документ"


def fields_for(kind: str) -> tuple[FieldSpec, ...]:
    schema = DOCUMENT_SCHEMAS.get(kind)
    return schema.fields if schema else DOCUMENT_SCHEMAS["arbitrary_template"].fields


def line_items_shape_for(kind: str) -> str | None:
    schema = DOCUMENT_SCHEMAS.get(kind)
    return schema.line_items_shape if schema else None


# ─── Quality-gate required fields — derived from DOCUMENT_SCHEMAS ──────────
#
# Built once at import time by filtering `required=True` — this reproduces
# the exact same (key, label, check) tuples that used to be hand-maintained
# here directly, so check_render_quality() in quality.py needs no changes.
# Money/items totals are intentionally not FieldSpec entries (see module
# docstring), so this filter can never accidentally introduce the
# items/total checks that already live in KINDS_WITH_TOTAL_ITEMS_CHECK.

# The unified schema's labels are deliberately Russian everywhere (matching
# the rest of the app's UI) — "Клиент / контрагент" instead of the legacy
# English "Client name" a few kinds' quality-gate messages used to show.
# That's a real (if cosmetic) label-text change for those kinds' QA issue
# messages; every other label below already matched exactly, and no
# scoring/blocking logic changes — see the PR description for the full
# before/after list rather than silently carrying stale English text
# forward just to claim zero diff.
def _required_tuple(fields: tuple[FieldSpec, ...]) -> tuple[RequiredField, ...]:
    return tuple(
        RequiredField(f.key, f.label, check=f.check)
        for f in fields if f.required
    )


UNIVERSAL_REQUIRED: tuple[RequiredField, ...] = _required_tuple(
    _kind_fields(_COMPANY_FIELDS, _SYSTEM_FIELDS),
)

# "arbitrary_template" is deliberately excluded here (matching the original
# hand-written dict, which never had an entry for it either) so
# required_fields_for() keeps falling back to DEFAULT_REQUIRED_FIELDS for
# it — an explicit empty tuple would instead silently drop that fallback's
# client_name requirement.
KIND_REQUIRED_FIELDS: dict[str, tuple[RequiredField, ...]] = {
    kind: _required_tuple(tuple(
        f for f in schema.fields
        if f not in _COMPANY_FIELDS and f not in _SYSTEM_FIELDS
    ))
    for kind, schema in DOCUMENT_SCHEMAS.items()
    if kind != "arbitrary_template"
}

# Kinds not declared above (any future kind someone forgets to register)
# fall back to this minimal set rather than silently checking nothing.
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
