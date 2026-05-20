"""Pluggable document renderers.

A `Renderer` takes a template body + context and returns ``(bytes, mime, ext)``.
Renderers are selected by the template's ``format`` field. New formats plug in
without touching invoice/document service code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Renderer(ABC):
    format: str  # "html" | "docx" | "pdf"

    @abstractmethod
    def render(self, *, body: str, context: dict[str, Any]) -> tuple[bytes, str, str]: ...


def get_renderer(fmt: str) -> Renderer:
    from app.services.documents.render.html import HTMLRenderer
    from app.services.documents.render.docx import DocxRenderer
    from app.services.documents.render.pdf import PDFRenderer
    return {"html": HTMLRenderer(), "docx": DocxRenderer(), "pdf": PDFRenderer()}[fmt]
