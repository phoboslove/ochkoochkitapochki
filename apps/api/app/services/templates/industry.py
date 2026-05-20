"""Industry classification for templates — heuristic, deterministic.

Inputs: filename + extracted paragraphs. Output: one of `INDUSTRIES`.
Never auto-confirmed silently — exposed in UI as suggestion + manual override.
"""
from __future__ import annotations

import re


INDUSTRIES = [
    "construction", "logistics", "manufacturing",
    "retail", "services", "agriculture", "finance", "general",
]


_KEYWORDS: dict[str, list[str]] = {
    "construction": [
        "монтаж", "строительн", "ремонт", "реконструкц", "modernization",
        "construction", "installation", "құрылыс", "монтаждау",
    ],
    "logistics": [
        "транспорт", "перевозк", "товарно-транспортн", "накладн",
        "перемещен", "доставк", "жүкқұжат", "тасымал",
    ],
    "manufacturing": [
        "производств", "сырь", "комплектующ", "оборудован",
        "цех", "manufacturing", "өндіріс",
    ],
    "retail": [
        "розничн", "магазин", "точка прода", "касс", "retail",
        "товарооборот", "бөлшек",
    ],
    "agriculture": [
        "сельскохоз", "биологическ", "урожа", "посев", "скот", "ферм",
        "agriculture", "ауыл шаруашылығы", "малшаруашылық",
    ],
    "finance": [
        "доверенность", "финансов", "банк", "налог",
        "ндс", "оплат", "счет на оплату", "счёт на оплату",
        "сенімхат", "қаржы", "салық",
    ],
    "services": [
        "оказани", "услуг", "выполненн", "consulting", "сервис",
        "көрсетіл", "қызмет",
    ],
}


def classify_industry(filename: str, paragraphs: list[str]) -> str:
    haystack = (filename or "").lower() + " " + " ".join(paragraphs[:40]).lower()
    scores: dict[str, int] = {}
    for industry, words in _KEYWORDS.items():
        scores[industry] = sum(haystack.count(w) for w in words)
    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else "general"
