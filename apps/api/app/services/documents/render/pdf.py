"""PDF renderer — HTML→PDF via WeasyPrint when available."""
from __future__ import annotations

from typing import Any

from app.services.documents.render import Renderer
from app.services.documents.render.html import HTMLRenderer


class PDFRenderer(Renderer):
    format = "pdf"

    def render(self, *, body: str, context: dict[str, Any]) -> tuple[bytes, str, str]:
        try:
            from weasyprint import HTML  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "PDF rendering requires WeasyPrint. "
                "Install with `pip install weasyprint`. The HTML renderer is the fallback.",
            ) from exc
        html_bytes, _mime, _ext = HTMLRenderer().render(body=body, context=context)
        pdf_bytes = HTML(string=html_bytes.decode("utf-8")).write_pdf()
        return pdf_bytes, "application/pdf", "pdf"
