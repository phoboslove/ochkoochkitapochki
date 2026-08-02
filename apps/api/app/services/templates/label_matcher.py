"""Label → canonical-field matching — semantic embeddings, substring fallback.

Both the template analyzer (suggesting field mappings for the mapping wizard)
and the legacy-template adapter (injecting {{anchors}} next to human labels
like "Поставщик:") used to run their OWN hardcoded substring dictionary
(``SYNONYMS`` in placeholders.py, ``ANCHOR_LIBRARY`` in generation/adapter.py)
over the same underlying problem: "what canonical field does this label
mean?". Both dictionaries only recognised RU/KZ/EN accounting vocabulary —
any other language, or a label phrased differently, scored zero.

This module replaces both call sites with one embedding-based matcher:
  * canonical fields are embedded once (from their human ``label`` in
    ``placeholders.CANONICAL``) and cached for the process lifetime;
  * candidate labels are embedded in a single batched call per
    analysis/adaptation run;
  * cosine similarity above ``MATCH_THRESHOLD`` wins.

When no AI key is configured, or the embeddings call fails, matching falls
back to ``placeholders.suggest()`` — the same substring table both call
sites used before this change, so behavior with no AI key is unchanged.
"""
from __future__ import annotations

import math

from app.core.config import settings
from app.core.logging import log
from app.services.templates.placeholders import CANONICAL, SYNONYMS, suggest

# Calibrated empirically against real RU/KZ/EN labels (see PR notes): raw
# text-embedding-3-small cosine similarity for short 2-4 word labels sits in
# a noisy 0.25-0.55 band with weak separation between right and wrong
# matches. 0.42 is where genuine matches ("Поставщик"→company_name 0.51,
# "Тапсырыс беруші"→client_name 0.44, "Total due"→total 0.49) separate from
# ambiguous ones. Below threshold, the substring fallback in
# ``placeholders.suggest`` still catches known RU/KZ/EN vocabulary — this is
# deliberately biased toward precision over recall: injecting a value into
# the wrong field of a real business document is worse than leaving a slot
# for manual mapping.
MATCH_THRESHOLD = 0.42
_EMBEDDING_MODEL = "text-embedding-3-small"

# A handful of core Kazakh accounting terms per canonical field. This is NOT
# an exhaustive translation table (that's the substring-matching trap this
# module exists to get away from) — it's a small set of anchor points in
# embedding space so cosine similarity has *some* Kazakh signal to align
# against. A differently-phrased Kazakh label the model has never seen still
# matches by proximity to these anchors; it doesn't need an exact hit.
_KZ_SEED: dict[str, list[str]] = {
    "company_name":     ["Жеткізуші", "Орындаушы", "Сатушы"],
    "company_bin":       ["Жеткізушінің БСН", "БСН"],
    "company_address":  ["Жеткізушінің мекенжайы"],
    "client_name":       ["Тапсырыс беруші", "Сатып алушы", "Алушы"],
    "client_bin":        ["Сатып алушының БСН"],
    "director_name":     ["Директор"],
    "accountant_name":   ["Бас бухгалтер"],
    "invoice_number":    ["Құжат нөмірі", "Шот-фактура №"],
    "invoice_date":      ["Құжат күні", "Жасалған күні"],
    "due_date":          ["Төлеу мерзімі"],
    "currency":          ["Валюта", "Теңге"],
    "vat":               ["ҚҚС"],
    "total":             ["Төленуге тиіс сома", "Барлығы", "Жиыны"],
    "items":             ["Тауарлар мен қызметтер"],
}

# Populated lazily on first use, cached for the process lifetime — the
# canonical field set never changes at runtime.
_canonical_vectors: dict[str, list[float]] | None = None


def _canonical_embedding_text(key: str) -> str:
    """Build the text embedded for one canonical field: its human label, a
    handful of RU synonyms already known for it (from placeholders.SYNONYMS
    — reused as embedding context, not as a substring rule), and a small
    Kazakh seed. More languages == more anchor phrases here, not more code."""
    field = CANONICAL[key]
    ru_synonyms = [pattern for pattern, canonical_key, _ in SYNONYMS if canonical_key == key]
    parts = [field.label, key.replace("_", " "), *ru_synonyms[:6], *_KZ_SEED.get(key, [])]
    seen: list[str] = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return " / ".join(seen)


async def match_labels_batch(
    labels: list[str],
) -> dict[str, tuple[str, float] | None]:
    """Resolve every distinct label to (canonical_key, confidence) or None.

    Labels are matched in this order:
      1. exact ``{{placeholder}}`` text → direct canonical hit (free, no AI).
      2. embeddings, when an AI key is configured.
      3. substring fallback (``placeholders.suggest``) for anything
         embeddings didn't confidently resolve, or when no AI key is set.
    """
    result: dict[str, tuple[str, float] | None] = {}
    remaining: dict[str, str] = {}
    for raw in labels:
        label = (raw or "").strip()
        if not label:
            result[raw] = None
            continue
        cleaned = label.strip("{} ").replace(" ", "_")
        if cleaned in CANONICAL:
            result[raw] = (cleaned, 1.0)
            continue
        remaining[raw] = label

    if not remaining:
        return result

    if not settings.openai_api_key:
        for raw, label in remaining.items():
            result[raw] = suggest(label)
        return result

    try:
        await _ensure_canonical_vectors()
        assert _canonical_vectors is not None
        keys = list(remaining.keys())
        vectors = await _embed_batch(list(remaining.values()))
        for raw, vec in zip(keys, vectors):
            best_key, best_score = None, 0.0
            for ck, cvec in _canonical_vectors.items():
                score = _cosine(vec, cvec)
                if score > best_score:
                    best_key, best_score = ck, score
            if best_key and best_score >= MATCH_THRESHOLD:
                result[raw] = (best_key, round(best_score, 3))
            else:
                # Embeddings weren't confident — try the substring table
                # before giving up (catches exact accounting terms that
                # happen to embed ambiguously, e.g. very short labels).
                result[raw] = suggest(remaining[raw])
    except Exception as exc:  # noqa: BLE001
        log.warning("label_embedding_failed", error=str(exc))
        for raw, label in remaining.items():
            result[raw] = suggest(label)

    return result


async def _ensure_canonical_vectors() -> None:
    global _canonical_vectors
    if _canonical_vectors is not None:
        return
    keys = list(CANONICAL.keys())
    texts = [_canonical_embedding_text(k) for k in keys]
    vectors = await _embed_batch(texts)
    _canonical_vectors = dict(zip(keys, vectors))


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.embeddings.create(model=_EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)
