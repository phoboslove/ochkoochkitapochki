"""PDF rendering engines.

Two real backends, picked at startup in this order:
  1. **WeasyPrint** — best fidelity (CSS @page, page-breaks, headers/footers,
     font embedding). Needs cairo/pango/gobject — readily available on Linux
     and in our Dockerfile (prod target); broken on most Windows machines without GTK.
  2. **xhtml2pdf** — pure-Python (ReportLab + html5lib). Lower fidelity but
     works everywhere with `pip install`. Suitable for development and as a
     Windows fallback.

The first import that successfully renders a 1-byte test wins. Diagnostics are
surfaced through ``engine_status()`` to /health/diagnostics so the UI can show
which engine is active and why.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from time import perf_counter
from typing import Any


@dataclass
class EngineStatus:
    name: str                  # weasyprint | xhtml2pdf | none
    available: bool
    error: str | None
    notes: list[str]


def render_pdf(html: str) -> tuple[bytes, dict[str, Any]]:
    """Render HTML to a PDF bytes blob. Returns (bytes, meta).

    `meta` always contains ``engine`` and ``duration_ms``; for failures it
    raises RuntimeError with the specific reason.
    """
    engine = _pick_engine()
    if not engine.available:
        raise RuntimeError(engine.error or "no PDF engine available")
    start = perf_counter()
    if engine.name == "weasyprint":
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
    elif engine.name == "xhtml2pdf":
        from xhtml2pdf import pisa
        out = BytesIO()
        pisa_status = pisa.CreatePDF(src=html, dest=out, encoding="utf-8")
        if pisa_status.err:
            raise RuntimeError(f"xhtml2pdf reported {pisa_status.err} error(s)")
        pdf = out.getvalue()
    else:
        raise RuntimeError(f"unknown engine: {engine.name}")
    duration_ms = int((perf_counter() - start) * 1000)
    return pdf, {"engine": engine.name, "duration_ms": duration_ms, "bytes": len(pdf)}


def engine_status() -> EngineStatus:
    return _pick_engine()


_cached: EngineStatus | None = None


def _pick_engine(force: bool = False) -> EngineStatus:
    global _cached
    if _cached is not None and not force:
        return _cached
    # WeasyPrint first.
    try:
        from weasyprint import HTML  # type: ignore
        # Force a trivial render to validate native libs.
        HTML(string="<p>ok</p>").write_pdf()
        _cached = EngineStatus("weasyprint", True, None,
                                ["Full-fidelity CSS @page + pagination."])
        return _cached
    except Exception as exc:  # noqa: BLE001
        weasy_err = str(exc).splitlines()[0][:240]
    # xhtml2pdf fallback.
    try:
        from xhtml2pdf import pisa  # type: ignore
        out = BytesIO()
        pisa.CreatePDF(src="<p>ok</p>", dest=out)
        if out.getvalue().startswith(b"%PDF"):
            _cached = EngineStatus(
                "xhtml2pdf", True, None,
                [f"WeasyPrint unavailable: {weasy_err}",
                 "xhtml2pdf active (lower fidelity; pure-Python)."],
            )
            return _cached
    except Exception as exc:  # noqa: BLE001
        xhtml_err = str(exc).splitlines()[0][:240]
    else:
        xhtml_err = "xhtml2pdf produced empty output"

    _cached = EngineStatus(
        "none", False,
        "No PDF engine available. Install WeasyPrint (Linux: works out of the "
        "box; Windows: install MSYS2 GTK runtime per WeasyPrint docs) or "
        "`pip install xhtml2pdf` as a fallback.",
        [f"weasyprint: {weasy_err}", f"xhtml2pdf: {xhtml_err}"],
    )
    return _cached
