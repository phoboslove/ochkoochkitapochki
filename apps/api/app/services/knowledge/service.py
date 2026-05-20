"""Knowledge base — keyword retrieval today, semantic-ready tomorrow."""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeDoc


_WORD_RE = re.compile(r"[\w\-]{3,}", re.UNICODE)


class KnowledgeService:
    async def list(self, session: AsyncSession, company_id: str) -> list[KnowledgeDoc]:
        rows = await session.scalars(
            select(KnowledgeDoc).where(KnowledgeDoc.company_id == company_id)
            .order_by(desc(KnowledgeDoc.created_at)),
        )
        return list(rows)

    async def get(self, session: AsyncSession, company_id: str, doc_id: str) -> KnowledgeDoc | None:
        doc = await session.get(KnowledgeDoc, doc_id)
        if not doc or doc.company_id != company_id:
            return None
        return doc

    async def upsert(
        self, session: AsyncSession, *, company_id: str, actor_id: str,
        title: str, body: str = "", tags: list[str] | None = None,
        storage_key: str | None = None, mime: str | None = None,
        doc_id: str | None = None,
    ) -> KnowledgeDoc:
        if doc_id:
            doc = await self.get(session, company_id, doc_id)
            if doc:
                doc.title = title; doc.body = body
                doc.tags = tags or []; doc.storage_key = storage_key; doc.mime = mime
                await session.flush()
                return doc
        doc = KnowledgeDoc(
            id=f"kb_{uuid.uuid4().hex[:10]}", company_id=company_id,
            title=title, body=body, tags=tags or [],
            storage_key=storage_key, mime=mime, created_by=actor_id,
        )
        session.add(doc)
        await session.flush()
        return doc

    async def delete(self, session: AsyncSession, company_id: str, doc_id: str) -> bool:
        doc = await self.get(session, company_id, doc_id)
        if not doc:
            return False
        await session.delete(doc)
        return True

    async def retrieve(
        self, session: AsyncSession, *, company_id: str, query: str, limit: int = 3,
    ) -> list[dict[str, Any]]:
        """Lightweight keyword retrieval. Returns ranked snippets the AI can quote."""
        terms = list({w.lower() for w in _WORD_RE.findall(query)})[:8]
        if not terms:
            return []
        clauses = [or_(
            func.lower(KnowledgeDoc.title).like(f"%{t}%"),
            func.lower(KnowledgeDoc.body).like(f"%{t}%"),
        ) for t in terms]
        rows = list(await session.scalars(
            select(KnowledgeDoc).where(
                KnowledgeDoc.company_id == company_id, or_(*clauses),
            ).limit(20),
        ))
        scored: list[tuple[int, KnowledgeDoc]] = []
        for d in rows:
            blob = (d.title + " \n " + (d.body or "")).lower()
            score = sum(blob.count(t) for t in terms)
            if score: scored.append((score, d))
        scored.sort(key=lambda x: -x[0])
        out: list[dict[str, Any]] = []
        for _, d in scored[:limit]:
            snippet = _make_snippet(d.body or "", terms)
            out.append({"id": d.id, "title": d.title, "snippet": snippet, "tags": d.tags})
        return out


def _make_snippet(body: str, terms: list[str], width: int = 240) -> str:
    if not body:
        return ""
    lower = body.lower()
    pos = min((lower.find(t) for t in terms if lower.find(t) != -1), default=0)
    start = max(0, pos - 60)
    end = min(len(body), start + width)
    s = body[start:end].strip()
    if start > 0: s = "… " + s
    if end < len(body): s = s + " …"
    return s
