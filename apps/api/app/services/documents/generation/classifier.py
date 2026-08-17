"""Document-kind classification — LLM structured output, regex fallback.

Replaces the old ``_KIND_LEXICON`` substring table that used to live inline
in ``intent.py``: instead of scanning the prompt for a fixed list of RU/EN/KZ
keywords, an OpenAI structured-JSON call reasons over the whole request in
whatever language it was written in.

When no AI key is configured (or the LLM call raises), classification falls
back to the exact keyword table that shipped before this change — same
kinds, same keywords, same behavior. This mirrors how the rest of the AI
orchestrator degrades: regex is the safety net, not the primary path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.logging import log

SUPPORTED_KINDS = [
    "invoice", "act", "nakladnaya", "contract", "trust_letter",
    "contract_services", "contract_supply", "act_reconciliation",
    "hr_order", "employment_contract",
]

# Fallback keyword table — used verbatim when no AI key is configured, or
# when the LLM call fails for any reason. This is the same table that used
# to be `_KIND_LEXICON` in intent.py; kept here since kind classification
# now lives in one place.
#
# Order matters: this is a first-match scan, and several new keyword sets
# are substrings of an older, more generic entry (e.g. "акт сверки"
# contains "акт", "договор поставки" contains "договор"). The specific
# entries are listed BEFORE their generic counterpart so they win.
KIND_LEXICON: list[tuple[str, list[str]]] = [
    ("invoice",      ["invoice", "счет", "счёт", "счет на оплату", "инвойс", "bill"]),
    ("act_reconciliation", ["акт сверки", "сверка взаиморасчет", "сверка взаиморасчёт",
                             "reconciliation act"]),
    ("act",          ["акт", "act of", "act for", "акт выполненных", "акт оказанных"]),
    ("nakladnaya",   ["накладн", "nakladnaya", "товарная накладная", "тн", "торг-12"]),
    ("contract_services", ["договор оказания услуг", "договор на оказание услуг",
                            "оказание услуг", "service agreement"]),
    ("contract_supply",   ["договор поставки", "договор на поставку", "поставка товара",
                            "supply agreement"]),
    ("employment_contract", ["трудовой договор", "employment contract", "labor contract",
                              "labour contract"]),
    ("hr_order",     ["приказ о приеме", "приказ о приёме", "приказ на работу",
                       "hiring order", "employment order"]),
    ("contract",     ["контракт", "договор", "contract", "agreement"]),
    ("trust_letter", ["доверенность на получение", "доверенность", "trust letter",
                       "power of attorney"]),
]


@dataclass
class KindClassification:
    kind: str | None
    confidence: float          # 0..1
    matched: list[str] = field(default_factory=list)
    source: str = "regex"      # "llm" | "regex"


async def classify_kind(text: str) -> KindClassification:
    """Best-effort kind classification. Never raises — worst case returns
    an empty (kind=None) classification, same as the old lexicon miss."""
    if not text or not text.strip():
        return KindClassification(None, 0.0, [], "regex")
    if settings.openai_api_key:
        try:
            return await _classify_via_llm(text)
        except Exception as exc:  # noqa: BLE001
            log.warning("kind_classification_llm_failed", error=str(exc))
    return _classify_via_regex(text)


async def _classify_via_llm(text: str) -> KindClassification:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = (
        "Classify a request to generate a business document. The request "
        "can be written in ANY language — do not assume Russian/English/"
        "Kazakh. Return STRICT JSON only, no commentary:\n"
        '{ "kind": one of ["invoice","act","nakladnaya","contract",'
        '"trust_letter","contract_services","contract_supply",'
        '"act_reconciliation","hr_order","employment_contract","unknown"],\n'
        '  "confidence": 0.0-1.0,\n'
        '  "matched_phrase": str (the phrase, IN THE ORIGINAL LANGUAGE, '
        'that signalled the kind — empty string if none) }\n\n'
        "Notes: act_reconciliation is a running-balance ledger of debits/"
        "credits between two parties (акт сверки взаиморасчётов) — do NOT "
        "confuse with 'act' (акт выполненных работ, a one-off acceptance of "
        "delivered work/services). contract_services is a договор оказания "
        "услуг; contract_supply is a договор поставки (goods, not services). "
        "hr_order is a short internal приказ о приёме на работу; "
        "employment_contract is the full трудовой договор with the employee. "
        "Use plain 'contract' only when the document is neither a service "
        "nor a supply agreement.\n\n"
        f"Request:\n---\n{text[:1500]}\n---"
    )
    resp = await client.chat.completions.create(
        model=settings.ai_default_model, temperature=0.0, max_tokens=120,
        messages=[
            {"role": "system", "content": "You classify short business requests. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    parsed = json.loads(raw)
    kind = parsed.get("kind")
    if kind not in SUPPORTED_KINDS:
        kind = None
    confidence = min(max(float(parsed.get("confidence") or 0.0), 0.0), 1.0)
    phrase = (parsed.get("matched_phrase") or "").strip()
    return KindClassification(kind, confidence, [phrase] if phrase else [], "llm")


def _classify_via_regex(text: str) -> KindClassification:
    low = text.lower()
    for kind, keywords in KIND_LEXICON:
        hits = [k for k in keywords if k in low]
        if hits:
            return KindClassification(kind, 0.3, hits, "regex")
    return KindClassification(None, 0.0, [], "regex")
