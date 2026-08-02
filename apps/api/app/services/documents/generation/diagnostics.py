"""Structured render diagnostics — Phase 3.

Every stage of the pipeline appends ``RenderDiagnostic`` rows to a
``DiagnosticsCollector`` so the final ``Document.parsed.diagnostics`` payload
contains a complete, machine-readable record of what happened — what was
adapted, what was injected, what failed, and what an operator can do next.

Goal: no opaque "render failed" anywhere in the system.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# Severity levels match QualityIssue so the UI can render them uniformly.
SEVERITY_INFO    = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR   = "error"

# Pipeline stages (stable strings — surfaced in UI, do not rename casually).
STAGE_INTENT       = "intent"
STAGE_MATCH        = "match"
STAGE_ADAPTATION   = "adaptation"
STAGE_RENDER       = "render"
STAGE_PDF_EXPORT   = "pdf_export"
STAGE_STORAGE      = "storage"
STAGE_QUALITY      = "quality"
STAGE_APPROVAL     = "approval"


@dataclass
class RenderDiagnostic:
    stage: str                              # one of STAGE_*
    code: str                               # short machine code, e.g. "anchor_injected"
    message: str                             # operator-facing human description
    severity: str = SEVERITY_INFO
    template_id: str | None = None
    failed_field: str | None = None          # canonical placeholder name
    failed_placeholder: str | None = None    # literal {{...}} that broke
    table_index: int | None = None
    row_index: int | None = None
    render_engine: str | None = None         # docxtpl | openpyxl | weasyprint | xhtml2pdf | libreoffice
    exception: str | None = None             # truncated str(exc) for failures
    suggested_fix: str | None = None         # actionable hint for the operator
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Drop empty optional fields to keep the payload readable.
        return {k: v for k, v in d.items() if v not in (None, "", [], {})}


class DiagnosticsCollector:
    """In-memory accumulator. Cheap, safe to pass everywhere."""

    def __init__(self) -> None:
        self._entries: list[RenderDiagnostic] = []

    def add(self, d: RenderDiagnostic) -> None:
        self._entries.append(d)

    def info(self, stage: str, code: str, message: str, **kw: Any) -> None:
        self.add(RenderDiagnostic(stage=stage, code=code, message=message,
                                    severity=SEVERITY_INFO, **kw))

    def warn(self, stage: str, code: str, message: str, **kw: Any) -> None:
        self.add(RenderDiagnostic(stage=stage, code=code, message=message,
                                    severity=SEVERITY_WARNING, **kw))

    def error(self, stage: str, code: str, message: str, **kw: Any) -> None:
        self.add(RenderDiagnostic(stage=stage, code=code, message=message,
                                    severity=SEVERITY_ERROR, **kw))

    def extend(self, others: list[RenderDiagnostic]) -> None:
        self._entries.extend(others)

    @property
    def entries(self) -> list[RenderDiagnostic]:
        return list(self._entries)

    def as_payload(self) -> list[dict[str, Any]]:
        return [e.as_dict() for e in self._entries]

    def has_errors(self) -> bool:
        return any(e.severity == SEVERITY_ERROR for e in self._entries)

    def filter(self, *, stage: str | None = None, severity: str | None = None) -> list[RenderDiagnostic]:
        return [
            e for e in self._entries
            if (stage is None or e.stage == stage)
            and (severity is None or e.severity == severity)
        ]
