"""Loader for the structured 2026 KZ tax-rate config.

Single source of truth for every rate/threshold used by both the read-only
tax-knowledge chat tool and the deterministic salary/turnover calculators —
per the product requirement that rates live in one editable place, not
scattered across prompts or hardcoded in calculation functions.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_RATES_PATH = Path(__file__).resolve().parents[2] / "config" / "tax_rates_kz_2026.json"


@lru_cache(maxsize=1)
def load_rates() -> dict[str, Any]:
    """Parsed contents of tax_rates_kz_2026.json. Cached — the file is only
    read once per process; restart the API after editing rates."""
    return json.loads(_RATES_PATH.read_text(encoding="utf-8"))


def disclaimer() -> str:
    rates = load_rates()
    return f"{rates['disclaimer']} (ставки актуальны на {rates['last_verified']})"
