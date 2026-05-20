"""Search service.

Two providers behind the same surface:
  * Keyword (default) — SQL ILIKE/LIKE over invoices/clients/documents.
  * Semantic (stub)   — wire pgvector / a vector DB; returns empty until then.

Caller chooses ``mode``; the API combines both.
"""
from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Client, Document, Invoice


SearchType = Literal["all", "invoice", "client", "document"]


class SearchService:
    async def keyword(
        self, session: AsyncSession, *, company_id: str, q: str, type: SearchType = "all", limit: int = 25,
    ) -> dict[str, list[dict[str, Any]]]:
        like = f"%{q}%"
        out: dict[str, list[dict[str, Any]]] = {"invoices": [], "clients": [], "documents": []}

        if type in {"all", "invoice"}:
            rows = await session.scalars(
                select(Invoice).where(
                    Invoice.company_id == company_id,
                    or_(Invoice.number.ilike(like), Invoice.notes.ilike(like)),
                ).limit(limit),
            )
            out["invoices"] = [
                {"id": i.id, "number": i.number, "total": str(i.total),
                 "currency": i.currency, "status": i.status}
                for i in rows
            ]

        if type in {"all", "client"}:
            rows = await session.scalars(
                select(Client).where(
                    Client.company_id == company_id,
                    or_(Client.name.ilike(like), Client.bin.ilike(like),
                        Client.phone.ilike(like), Client.email.ilike(like)),
                ).limit(limit),
            )
            out["clients"] = [
                {"id": c.id, "name": c.name, "bin": c.bin, "phone": c.phone}
                for c in rows
            ]

        if type in {"all", "document"}:
            rows = await session.scalars(
                select(Document).where(
                    Document.company_id == company_id,
                    or_(Document.title.ilike(like), Document.ocr_text.ilike(like)),
                ).limit(limit),
            )
            out["documents"] = [
                {"id": d.id, "title": d.title, "type": d.type, "status": d.status}
                for d in rows
            ]
        return out

    async def semantic(
        self, session: AsyncSession, *, company_id: str, q: str, limit: int = 10,
    ) -> list[dict[str, Any]]:
        # Stub. Plug pgvector or a managed vector DB; embed `Document.ocr_text` on
        # status="PARSED" and search here. Returns [] until configured.
        return []
