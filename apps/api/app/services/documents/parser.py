"""Structured-field extraction from raw OCR text.

Strategy: deterministic regex/heuristics first, then optional LLM fallback for
ambiguous documents. Returns a typed dict per document type.
"""
from __future__ import annotations

import re
from typing import Any


def parse_invoice(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "invoice"}
    if m := re.search(r"#\s*([A-Z0-9\-]+)", text):
        out["number"] = m.group(1)
    if m := re.search(r"Total[:\s]+([\d,\.]+)", text, re.I):
        out["total"] = m.group(1).replace(",", "")
    return out


def parse(document_type: str, text: str) -> dict[str, Any]:
    match document_type.lower():
        case "invoice":
            return parse_invoice(text)
        case _:
            return {"type": document_type, "text_preview": text[:300]}
