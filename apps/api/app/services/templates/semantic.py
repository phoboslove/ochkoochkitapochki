"""Semantic enrichment of templates.

When OpenAI is configured, summarizes a few paragraphs into structured business
metadata. When unavailable, falls back to deterministic keyword extraction
(stopword-filtered Cyrillic / Latin tokens + cluster-keyword overlap).

Stored on `template.detected_fields["semantic"]` to avoid schema migrations:
    {
      "summary":         "Акт выполненных работ ...",
      "business_purpose":"Acceptance of services delivered to the client",
      "use_case":        "Закрытие услуг по договору",
      "tags":            ["act","services","acceptance"],
      "keywords":        ["приёмка","услуги","выполненных"],
      "probable_kind":     "act",
      "probable_industry": "services",
      "model": "gpt-3.5-turbo" | "fallback",
      "at":    "2026-05-20T12:34:56Z"
    }
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

from app.core.config import settings


# Russian/Kazakh + English stopwords (compact set — accountant-context heavy).
_STOPWORDS = set("""
а в во без на по при из как до или для но не и так что это если за от же
бы был была было были быть либо ли еще еще также также самый эта эти этот
the of a an in on at to and or for is are was were be been being by with as
осы бұл және деген үшін бойынша қана басқа
""".split())

_WORD_RE = re.compile(r"[А-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІіA-Za-z0-9]{3,}")

_TAG_RULES: list[tuple[str, list[str]]] = [
    # tag → trigger substrings (lowercase, partial-match)
    ("act",          ["акт", "акт выполн", "akt", "act of"]),
    ("acceptance",   ["приёмк", "приемк", "qabyldau", "қабылдау", "acceptance"]),
    ("invoice",      ["счет", "счёт", "shot", "invoice", "счёт-фактура"]),
    ("nakladnaya",   ["накладн", "жүкқұжат", "waybill"]),
    ("contract",     ["договор", "шарт", "contract", "agreement"]),
    ("inventory",    ["инвентар", "опись", "түгендеу"]),
    ("attorney",     ["доверенност", "сенімхат", "power of attorney"]),
    ("services",     ["услуг", "сервис", "қызмет"]),
    ("supply",       ["поставк", "поставщик товар", "жеткізу"]),
    ("reconciliation", ["сверк", "взаиморасчет", "взаиморасчёт", "салыстыру"]),
    ("hr",           ["приказ о приеме", "приказ о приёме", "трудовой договор", "кадр"]),
    ("logistics",    ["перевозк", "транспорт", "доставк", "тасымал"]),
    ("construction", ["монтаж", "строит", "ремонт", "құрылыс"]),
    ("agriculture",  ["биологическ", "сельскохоз", "скот", "ферм", "ауыл"]),
    ("retail",       ["розничн", "торгов", "магазин"]),
    ("manufacturing",["производств", "сырь", "цех"]),
    ("vat",          ["ндс", "vat"]),
    ("payment",      ["оплат", "to'lem", "platej", "к оплате"]),
    ("write_off",    ["списан", "вывод", "списания"]),
]


async def summarize(
    *, paragraphs: list[str], filename: str, kind: str, language: str | None,
) -> dict[str, Any]:
    """Run AI summarization when possible; otherwise return a heuristic result.

    Pure function — caller decides whether to persist.
    """
    text = "\n".join(paragraphs[:30])[:3500]   # cap input tokens
    keywords = _keywords(text)
    tags = _tags_from(text, filename)

    base: dict[str, Any] = {
        "tags": tags, "keywords": keywords[:24],
        "probable_kind": kind, "probable_industry": None,
        "at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

    if not settings.openai_api_key or not text.strip():
        return {
            **base, "model": "fallback",
            "summary":  _heuristic_summary(text, tags),
            "business_purpose": _heuristic_purpose(tags),
            "use_case": _heuristic_use_case(tags),
        }

    # LLM path: very small JSON-only prompt — kept cheap on gpt-3.5-turbo.
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        prompt = (
            "You classify Kazakhstani / Russian-language business document templates. "
            "Return STRICT JSON only — no commentary. Schema:\n"
            "{ \"summary\": str (≤180 chars, plain Russian or English),"
            "  \"business_purpose\": str (≤120 chars, what business outcome the doc supports),"
            "  \"use_case\": str (≤120 chars, concrete operational scenario),"
            "  \"probable_kind\": one of [invoice, act, nakladnaya, contract, proposal, other],"
            "  \"probable_industry\": one of [construction, logistics, manufacturing, retail, services, agriculture, finance, general],"
            "  \"tags\": [str up to 6, lowercase, hyphenated] }\n\n"
            f"Filename: {filename}\nDetected kind hint: {kind}\nLanguage: {language}\n"
            f"Extracted text (first paragraphs):\n---\n{text}\n---"
        )
        resp = await client.chat.completions.create(
            model=settings.ai_default_model, temperature=0.1, max_tokens=320,
            messages=[
                {"role": "system", "content": "You are a careful document-classification assistant. Output JSON only."},
                {"role": "user",   "content": prompt},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        # Strip ``` fences if any.
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
        parsed = json.loads(raw)
        merged_tags = list({*tags, *(parsed.get("tags") or [])})[:8]
        return {
            **base, "model": settings.ai_default_model,
            "summary":          (parsed.get("summary") or "").strip()[:240],
            "business_purpose": (parsed.get("business_purpose") or "").strip()[:160],
            "use_case":         (parsed.get("use_case") or "").strip()[:160],
            "probable_kind":     parsed.get("probable_kind") or kind,
            "probable_industry": parsed.get("probable_industry"),
            "tags":              merged_tags,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            **base, "model": f"fallback (LLM error: {str(exc)[:80]})",
            "summary":  _heuristic_summary(text, tags),
            "business_purpose": _heuristic_purpose(tags),
            "use_case": _heuristic_use_case(tags),
        }


# ─── Heuristics ──────────────────────────────────────────────────────────────

def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "") if w.lower() not in _STOPWORDS]


def _keywords(text: str, limit: int = 20) -> list[str]:
    c = Counter(_tokens(text))
    return [w for w, _ in c.most_common(limit)]


def _tags_from(text: str, filename: str) -> list[str]:
    hay = (text + " " + filename).lower()
    out: list[str] = []
    for tag, triggers in _TAG_RULES:
        if any(tr in hay for tr in triggers):
            out.append(tag)
    return out[:6]


def _heuristic_summary(text: str, tags: list[str]) -> str:
    first = (text.strip().split("\n", 1)[0] if text else "").strip()
    if first:
        return first[:180]
    return "Бизнес-документ KZ. Теги: " + ", ".join(tags or ["—"])


def _heuristic_purpose(tags: list[str]) -> str:
    mapping = {
        "invoice":    "Issue a payable invoice to a client",
        "act":        "Formalize acceptance of work / goods delivered",
        "nakladnaya": "Track goods movement between parties",
        "contract":   "Legal agreement between counterparties",
        "attorney":   "Authorize a representative to act on behalf",
        "inventory":  "Inventory accounting / write-off / reconciliation",
        "write_off":  "Formal disposal of company assets",
    }
    for t in tags:
        if t in mapping: return mapping[t]
    return "Operational accounting document"


def _heuristic_use_case(tags: list[str]) -> str:
    if "invoice" in tags:    return "Выставление счёта клиенту по договору"
    if "act" in tags:        return "Закрытие этапа работ / услуг"
    if "nakladnaya" in tags: return "Внутреннее перемещение / поставка ТМЦ"
    if "contract" in tags:   return "Заключение договора с контрагентом"
    if "inventory" in tags:  return "Периодическая инвентаризация активов"
    if "attorney" in tags:   return "Делегирование полномочий представителю"
    return "Операционный учётный документ"


# ─── Matcher helpers ────────────────────────────────────────────────────────

def semantic_score(template_semantic: dict | None, *, query: str) -> tuple[int, list[str]]:
    """How well does a template match a free-text user query?

    Returns (score 0..40, matched_terms). Uses tag overlap + keyword presence.
    """
    if not template_semantic:
        return 0, []
    q_tokens = set(_tokens(query))
    if not q_tokens:
        return 0, []
    tags = [t.lower() for t in (template_semantic.get("tags") or [])]
    kws  = [k.lower() for k in (template_semantic.get("keywords") or [])]
    summary_tokens = set(_tokens(template_semantic.get("summary") or ""))
    use_case_tokens = set(_tokens(template_semantic.get("use_case") or ""))

    matched: list[str] = []
    score = 0
    for q in q_tokens:
        if q in tags:                       score += 10; matched.append(q)
        elif q in kws:                      score += 5;  matched.append(q)
        elif q in summary_tokens:           score += 4;  matched.append(q)
        elif q in use_case_tokens:          score += 3;  matched.append(q)
    return min(score, 40), matched[:6]
