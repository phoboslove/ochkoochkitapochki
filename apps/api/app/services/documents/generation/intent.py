"""Intent parser for document-generation requests — any language.

Extracts: kind (invoice|act|nakladnaya|contract|trust_letter|arbitrary),
client name, total amount, currency, single-line item, VAT hint, date hint.

Kind classification goes through ``classifier.classify_kind`` — an LLM
structured-output call when an AI key is configured, a regex keyword table
otherwise (see classifier.py). Everything else here (amount, client,
line-items, VAT) stays a deterministic regex pass: it's fast, predictable,
and already guarded against LLM hallucination by the "parser wins" merge
rule in registry.py — there's no reason to route it through an LLM call.
The AI orchestrator can override any field by passing explicit args to the
``generate_document`` tool.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.services.documents.generation.classifier import classify_kind

_AMOUNT_RE = re.compile(
    r"(?P<amount>\d[\d  .,]{0,20})\s*(?P<cur>kzt|тг|тенге|₸|т\.|usd|\$|eur|€|руб|rub)?",
    re.IGNORECASE,
)
_CLIENT_RE = re.compile(
    # Connector + name, but the name MUST stay on the same line — using `\s+`
    # here used to slurp across newlines, swallowing the next paragraph
    # ("...для TOO Sigma\n\nУслуги:\n..." → client_name "TOO Sigma Услуги").
    # `[ \t]+` confines name extraction to a single line.
    r"(?:для|for|клиент(?:а|у)?|to|компании|company)[ \t]+"
    r"(?P<name>(?:TOO|ТОО|ИП|АО|TOV|LLP|LLC)[ \t]+[\w\-]+(?:[ \t]+[\w\-]+){0,3}"
    r"|[\"«][^\"»\n]+[\"»]"
    r"|[A-ZА-ЯЁ][\w\-]+(?:[ \t]+[A-ZА-ЯЁ\w\-]+){0,2})",
    re.IGNORECASE,
)
_QTY_RE = re.compile(r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?:шт|штук|pcs|x|×)\b", re.IGNORECASE)
_VAT_RE = re.compile(r"(?:ндс|vat)\s*(?P<pct>\d{1,2})?", re.IGNORECASE)
# Anchored to the salary keyword itself (unlike _AMOUNT_RE, which matches
# any bare digit run) — this is what lets a deterministic parse of "оклад
# 400000" win over an LLM's extra_fields.salary guess in registry.py's
# "parser wins" merge, instead of the two ever silently disagreeing.
_SALARY_RE = re.compile(
    r"(?:оклад|зарплат[аеу]|зп|salary)\s*[:\-—]?\s*"
    r"(?P<amount>\d[\d  .,]{0,20})\s*"
    r"(?P<cur>kzt|тг|тенге|₸|т\.|usd|\$|eur|€|руб|rub)?",
    re.IGNORECASE,
)

_CUR_MAP = {
    "kzt": "KZT", "тг": "KZT", "тенге": "KZT", "₸": "KZT", "т.": "KZT",
    "usd": "USD", "$": "USD",
    "eur": "EUR", "€": "EUR",
    "руб": "RUB", "rub": "RUB",
}


@dataclass
class IntentSpec:
    kind: str = "invoice"                # invoice|act|nakladnaya|contract|trust_letter|arbitrary_template
    client_name: str | None = None
    counterparty_name: str | None = None
    total: float | None = None
    salary: float | None = None
    currency: str = "KZT"
    item_description: str | None = None
    qty: float = 1.0
    vat_percent: float | None = None
    issue_date: date = field(default_factory=date.today)
    raw_text: str = ""
    confidence: float = 0.0
    kind_keywords_matched: list[str] = field(default_factory=list)
    # Multi-line items parsed out of the prompt (e.g. "разработка — 350000\nдизайн — 120000").
    parsed_items: list[dict] = field(default_factory=list)

    def line_items(self) -> list[dict]:
        # Multi-line items take precedence — when the user typed out a
        # structured list, the AI shouldn't collapse it into one row.
        if self.parsed_items:
            return self.parsed_items
        if not self.total:
            return []
        unit = self.total / self.qty if self.qty else self.total
        return [{
            "name": self.item_description or _default_item_name(self.kind),
            "qty": self.qty,
            "price": unit,
            "total": self.total,
        }]


def _default_item_name(kind: str) -> str:
    return {
        "invoice":      "Услуги",
        "act":          "Выполненные работы",
        "nakladnaya":   "Товар",
        "contract":     "Предмет договора",
        "trust_letter": "Доверенное действие",
    }.get(kind, "Позиция")


async def parse_intent(text: str) -> IntentSpec:
    """Best-effort parse. Always returns a spec — never raises.

    Unknown kind defaults to 'invoice' (the safest sink for a finance request).
    """
    spec = IntentSpec(raw_text=text)
    low = text.lower()

    # Kind — LLM structured-output classification when an AI key is
    # configured, regex keyword table otherwise (classifier.py owns both).
    classification = await classify_kind(text)
    if classification.kind:
        spec.kind = classification.kind
        spec.kind_keywords_matched = classification.matched
        weight = classification.confidence if classification.source == "llm" else 1.0
        spec.confidence += 0.3 * weight

    # Client.
    if m := _CLIENT_RE.search(text):
        raw = m.group("name").strip().strip('"«»')
        # Trim trailing clauses ("на сумму...", "for $...").
        raw = re.split(r"\s+(?:на\s+сумму|на|за|for|amount)", raw, flags=re.IGNORECASE)[0].strip()
        spec.client_name = raw.rstrip(".,")
        spec.confidence += 0.25

    # Amount + currency.
    amount_zone = re.sub(r"^.*?(?:на сумму|на|сумм|amount|total|итого|for)\s*", "",
                          text, count=1, flags=re.IGNORECASE)
    if m := _AMOUNT_RE.search(amount_zone):
        try:
            cleaned = m.group("amount").replace(" ", "").replace(" ", "").replace(",", ".")
            cleaned = cleaned.rstrip(".")
            spec.total = float(cleaned)
            spec.confidence += 0.25
            cur_raw = (m.group("cur") or "").lower()
            if cur_raw and cur_raw in _CUR_MAP:
                spec.currency = _CUR_MAP[cur_raw]
        except (ValueError, AttributeError):
            pass

    # Salary (оклад) — separate from the generic `total` above: an HR
    # document's salary and a commercial document's amount are unrelated
    # concepts that happen to both be bare numbers, so this needs its own
    # keyword-anchored match rather than reusing _AMOUNT_RE's zone-stripped
    # search (which only strips a fixed set of invoice-ish lead-in words).
    if m := _SALARY_RE.search(text):
        amount = _coerce_amount(m.group("amount"))
        if amount is not None:
            spec.salary = amount
            spec.confidence += 0.2

    # Qty / VAT.
    if m := _QTY_RE.search(text):
        try:
            spec.qty = float(m.group("qty").replace(",", "."))
        except ValueError:
            pass
    if m := _VAT_RE.search(text):
        if m.group("pct"):
            try:
                spec.vat_percent = float(m.group("pct"))
            except ValueError:
                pass

    # Multi-line items — "разработка — 350000\nдизайн — 120000" style.
    # When found, recompute total from parsed rows: the structured list is
    # canonical, and the earlier single-amount regex may have captured a
    # per-row figure or even a qty ("12 шт ...") as the document total.
    parsed_items = parse_line_items(text)
    if parsed_items:
        spec.parsed_items = parsed_items
        spec.confidence += 0.2
        spec.total = sum(it["total"] for it in parsed_items)

    # Labeled party extraction — handles "Клиент Никита / Контрагент Алихан"
    # style follow-ups that the connector-based _CLIENT_RE doesn't catch.
    # The connector regex (для / for / клиент X) usually wins for the
    # client; counterparty has no other source.
    labeled_client, labeled_counterparty = extract_parties(text)
    if labeled_client and not spec.client_name:
        spec.client_name = labeled_client
        spec.confidence += 0.05
    if labeled_counterparty:
        spec.counterparty_name = labeled_counterparty
        spec.confidence += 0.05

    spec.confidence = min(spec.confidence, 1.0)
    return spec


# ── Multi-line item parser ─────────────────────────────────────────────────
#
# Detects the common "Создай акт:\n  разработка — 350000\n  дизайн — 120000"
# pattern that comes from operators copy-pasting their own line-item lists.
# Each line must have a name part and an amount part separated by a dash,
# colon, em-dash, или Unicode hyphen.

_LINE_ITEM_RE = re.compile(
    r"^\s*[\-*•]?\s*"                              # optional bullet
    r"(?:(?P<qty>\d+(?:[.,]\d+)?)\s*(?:шт|штук|pcs)\s+)?"        # optional "12 шт "
    r"(?P<name>.{2,140}?)"                          # greedy-stop name
    r"\s+(?:[\-—–:│|]|[-]{1,3})\s+"                # separator MUST be wrapped in spaces
    r"(?P<amount>\d[\d  .,]{0,20})"                 # amount
    r"\s*(?P<cur>kzt|тг|тенге|₸|т\.|usd|\$|eur|€)?\s*$",
    re.IGNORECASE,
)

# Amount-first pattern — operators routinely type "80000 за приезд",
# "60000 — холодильник", "Сумма 80000 за установку". We treat anything that
# starts with a money-looking token and contains a description token after a
# preposition / dash as an item line.
_AMOUNT_FIRST_RE = re.compile(
    r"^\s*[\-*•]?\s*"
    r"(?:сумма|итого|стоимость|цена)?\s*"           # optional label prefix
    r"(?P<amount>\d[\d  .,]{1,20})"
    r"\s*(?P<cur>kzt|тг|тенге|₸|т\.|usd|\$|eur|€)?"
    r"\s+(?:за|на|—|–|-{1,3})\s+"                  # connector
    r"(?P<name>.{2,140}?)"
    r"\s*$",
    re.IGNORECASE,
)

# Labeled party lines: "Клиент Никита", "Контрагент: Алихан", "Заказчик — TOO X".
_PARTY_LABELS_CLIENT = (
    "клиент", "заказчик", "покупатель", "получатель",
)
_PARTY_LABELS_COUNTERPARTY = (
    "контрагент", "поставщик", "исполнитель", "продавец",
)
_PARTY_LINE_RE = re.compile(
    r"^\s*(?P<label>[А-Яа-яёЁ]{4,16})\s*[:\-—–]?\s+(?P<name>[^\n]{2,80})\s*$",
)


def extract_parties(text: str) -> tuple[str | None, str | None]:
    """Pull labeled client / counterparty out of a free-form message.

    Returns ``(client_name, counterparty_name)``. Either may be None.
    Looks at each line in isolation — does NOT consume lines that the
    item parser would consume.
    """
    client: str | None = None
    counterparty: str | None = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or len(line) < 6:
            continue
        # Skip lines that ALREADY look like item lines so we don't grab
        # "Сумма 80000 за приезд" as a party.
        if _LINE_ITEM_RE.match(line) or _AMOUNT_FIRST_RE.match(line):
            continue
        m = _PARTY_LINE_RE.match(line)
        if not m:
            continue
        label = m.group("label").lower()
        name = m.group("name").strip().rstrip(",.;:")
        if not name or any(ch.isdigit() for ch in name):
            continue
        if label in _PARTY_LABELS_CLIENT and not client:
            client = name
        elif label in _PARTY_LABELS_COUNTERPARTY and not counterparty:
            counterparty = name
    return client, counterparty


_SKIP_PREFIXES = (
    "создай", "создать", "выстав", "сделай", "сформируй", "сгенери", "давай",
    "клиент", "заказчик", "контрагент", "поставщик", "исполнитель", "покупатель",
    "для ",
)


def _coerce_amount(raw: str) -> float | None:
    try:
        cleaned = raw.replace(" ", "").replace(" ", "").replace(",", ".").rstrip(".")
        v = float(cleaned)
        return v if v > 0 else None
    except (ValueError, AttributeError):
        return None


def parse_line_items(text: str) -> list[dict]:
    """Parse multi-line items out of a prompt.

    Three syntactic forms are recognised, in this priority per-line:

      A. name-first       "разработка CRM — 350000"      → item
      B. amount-first     "60000 за холодильник"          → item
      C. amount-first
         with label       "Сумма 80000 за приезд"         → item

    Conservative skip list: lines that begin with a generation verb
    ("создай", "сделай", "сформируй"), a party label ("Клиент",
    "Контрагент"), or are too short — they go to other extractors
    (parties / kind).

    Returns [] when fewer than 1 valid row was found (caller decides
    whether 1 item is enough — single-item prompts have a separate path
    in build_canonical_context).
    """
    items: list[dict] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or len(line) < 4:
            continue
        low = line.lower()
        # Skip kind/intent/party label lines, but ONLY when the rest of
        # the line is NOT clearly amount-bearing — "Сумма 80000 за..."
        # has the "сумма" prefix but is a valid item line.
        if any(low.startswith(k) for k in _SKIP_PREFIXES):
            # Re-check: party label lines never contain a money token
            # AND don't start with a prefix the amount-first regex handles.
            if not any(c.isdigit() for c in line):
                continue
            # If digits are present but it's a "Клиент XX" line with phone
            # numbers or BINs, the amount-first regex below won't match
            # and we'll skip it correctly.

        m = _LINE_ITEM_RE.match(line)
        if m:
            amount = _coerce_amount(m.group("amount"))
            if amount is None:
                continue
            name = m.group("name").strip().strip(",.;").strip()
            if not name or len(name) < 2:
                continue
            qty_raw = m.group("qty")
            qty = 1.0
            if qty_raw:
                try:    qty = float(qty_raw.replace(",", "."))
                except ValueError: qty = 1.0
            price = amount / qty if qty else amount
            items.append({"name": name, "qty": qty, "price": price, "total": amount})
            continue

        m = _AMOUNT_FIRST_RE.match(line)
        if m:
            amount = _coerce_amount(m.group("amount"))
            if amount is None:
                continue
            name = (m.group("name") or "").strip().strip(",.;").strip()
            if not name or len(name) < 2:
                continue
            items.append({"name": name, "qty": 1.0, "price": amount, "total": amount})
            continue
    # Return everything found — caller decides whether to require >=2.
    return items
