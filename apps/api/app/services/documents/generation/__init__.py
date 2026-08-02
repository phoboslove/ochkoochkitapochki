"""Operational document generation pipeline (Phase 1+2+5).

End-to-end flow: NL request → intent → template match → canonical context
→ DOCX/XLSX render → PDF export → storage → Document row → audit → approval.

Entrypoint: ``GenerationPipeline.generate``. Not invoice-specific.
"""
from app.services.documents.generation.pipeline import (
    GenerationPipeline,
    GenerationResult,
    SUPPORTED_KINDS,
)
from app.services.documents.generation.intent import IntentSpec, parse_intent

__all__ = [
    "GenerationPipeline", "GenerationResult", "SUPPORTED_KINDS",
    "IntentSpec", "parse_intent",
]
