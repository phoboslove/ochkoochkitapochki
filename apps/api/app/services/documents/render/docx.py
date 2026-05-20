"""DOCX renderer — production swaps to ``docxtpl`` / python-docx.

The body field is treated as the storage key of a ``.docx`` template; the
context fills the bookmarks. Keeping this as a thin adapter so the rest of
the system is renderer-agnostic.
"""
from __future__ import annotations

from typing import Any

from app.services.documents.render import Renderer


class DocxRenderer(Renderer):
    format = "docx"

    def render(self, *, body: str, context: dict[str, Any]) -> tuple[bytes, str, str]:
        try:
            from docxtpl import DocxTemplate  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "DOCX rendering requires `docxtpl` (and a template stored as a .docx). "
                "Install with `pip install docxtpl`.",
            ) from exc

        # `body` is expected to be a storage key pointing at the .docx template.
        from app.services.storage import get_storage
        template_bytes = get_storage().get(body)

        from io import BytesIO
        tpl = DocxTemplate(BytesIO(template_bytes))
        tpl.render(context)
        out = BytesIO()
        tpl.save(out)
        return (
            out.getvalue(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )
