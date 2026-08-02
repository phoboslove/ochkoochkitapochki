"""Template service — per-company template library with lifecycle + versioning."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Template
from app.services.audit.logger import AuditLogger
from app.services.templates.analyzer import analyze
from app.services.templates.industry import classify_industry
from app.services.templates.placeholders import CANONICAL


def _id() -> str:
    return f"tpl_{uuid.uuid4().hex[:10]}"


class TemplateService:
    def __init__(self) -> None:
        self.audit = AuditLogger()

    # ── Reads ──────────────────────────────────────────────────────────────

    async def list(
        self, session: AsyncSession, company_id: str, kind: str | None = None,
    ) -> list[Template]:
        q = select(Template).where(Template.company_id == company_id)
        if kind:
            q = q.where(Template.kind == kind)
        rows = await session.scalars(q.order_by(desc(Template.updated_at)))
        return list(rows)

    async def get(self, session: AsyncSession, company_id: str, tpl_id: str) -> Template | None:
        tpl = await session.get(Template, tpl_id)
        if not tpl or tpl.company_id != company_id:
            return None
        return tpl

    async def get_default(self, session: AsyncSession, company_id: str, kind: str) -> Template | None:
        return await session.scalar(
            select(Template).where(
                Template.company_id == company_id,
                Template.kind == kind,
                Template.is_default == True,  # noqa: E712
                Template.status != "ARCHIVED",
            ),
        )

    async def versions(self, session: AsyncSession, company_id: str, tpl_id: str) -> list[Template]:
        head = await self.get(session, company_id, tpl_id)
        if not head: return []
        family_root = head.parent_template_id or head.id
        rows = await session.scalars(
            select(Template).where(
                Template.company_id == company_id,
                ((Template.id == family_root) | (Template.parent_template_id == family_root)),
            ).order_by(desc(Template.version)),
        )
        return list(rows)

    # ── Writes ─────────────────────────────────────────────────────────────

    async def upsert(
        self, session: AsyncSession, *, company_id: str,
        id: str | None, name: str, kind: str, format: str, body: str, is_default: bool = False,
    ) -> Template:
        if is_default:
            for t in await self.list(session, company_id, kind):
                if t.is_default and t.id != id:
                    t.is_default = False
        if id:
            tpl = await session.get(Template, id)
            if tpl and tpl.company_id == company_id:
                tpl.name, tpl.kind, tpl.format, tpl.body, tpl.is_default = name, kind, format, body, is_default
                tpl.updated_at = datetime.utcnow()
                return tpl
        tpl = Template(
            id=_id(), company_id=company_id, name=name, kind=kind,
            format=format, body=body, is_default=is_default, status="UPLOADED",
        )
        session.add(tpl)
        await session.flush()
        return tpl

    async def ingest(
        self, session: AsyncSession, *, company_id: str, actor_id: str,
        name: str, filename: str, mime: str, storage_key: str, content: bytes,
        is_default: bool = False,
    ) -> Template:
        """Ingest one file: persist, analyze, suggest mappings — atomic per file."""
        analysis = await analyze(content, mime=mime, filename=filename)

        # De-duplicate by hash → bump version of the existing family.
        existing = await session.scalar(
            select(Template).where(
                Template.company_id == company_id,
                Template.file_hash == analysis.file_hash,
            ),
        )
        if existing:
            await self.audit.record(
                session, company_id=company_id, actor_type="user", actor_id=actor_id,
                action="template.duplicate_detected", resource=existing.id,
                meta={"filename": filename, "hash": analysis.file_hash[:10]},
            )
            return existing

        industry = classify_industry(filename, analysis.paragraphs)
        tpl = Template(
            id=_id(), company_id=company_id, name=name,
            kind=analysis.kind if analysis.kind != "unknown" else "invoice",
            format=analysis.format, body=storage_key,
            is_default=is_default, status="ANALYZED",
            original_filename=filename, file_hash=analysis.file_hash,
            language=analysis.language, version=1,
            detected_fields={"paragraphs": analysis.paragraphs[:60],
                             "placeholders": analysis.placeholders,
                             "notes": analysis.notes},
            detected_tables=[t for t in analysis.to_dict()["tables"]],
            mappings=analysis.suggestions,
            confidence=analysis.confidence,
            industry=industry,
        )
        session.add(tpl)
        if is_default:
            for other in await self.list(session, company_id, tpl.kind):
                if other.is_default and other.id != tpl.id:
                    other.is_default = False
        await self.audit.record(
            session, company_id=company_id, actor_type="user", actor_id=actor_id,
            action="template.uploaded", resource=tpl.id,
            meta={"filename": filename, "kind": tpl.kind, "format": tpl.format, "lang": tpl.language},
        )
        await self.audit.record(
            session, company_id=company_id, actor_type="system",
            action="template.analyzed", resource=tpl.id,
            meta={"suggestions": len(analysis.suggestions), "tables": len(analysis.tables),
                  "confidence": tpl.confidence},
        )
        await session.flush()
        return tpl

    async def reanalyze(self, session: AsyncSession, tpl: Template, content: bytes) -> Template:
        analysis = await analyze(content, mime="", filename=tpl.original_filename or tpl.name)
        tpl.detected_fields = {"paragraphs": analysis.paragraphs[:60],
                               "placeholders": analysis.placeholders,
                               "notes": analysis.notes}
        tpl.detected_tables = analysis.to_dict()["tables"]
        # Preserve confirmed mappings, refresh unconfirmed ones.
        preserved = {k: v for k, v in (tpl.mappings or {}).items() if v.get("confirmed")}
        tpl.mappings = {**analysis.suggestions, **preserved}
        tpl.confidence = analysis.confidence
        tpl.status = "ANALYZED" if not preserved else "MAPPED"
        return tpl

    async def update_mappings(
        self, session: AsyncSession, tpl: Template, *,
        mappings: dict[str, dict[str, Any]], confirm_all: bool = False, actor_id: str,
    ) -> Template:
        current = tpl.mappings or {}
        for key, m in mappings.items():
            if key not in CANONICAL: continue
            cur = current.get(key, {})
            current[key] = {
                "source_label": m.get("source_label", cur.get("source_label", "")),
                "source_kind":  m.get("source_kind",  cur.get("source_kind", "manual")),
                "confidence":   float(m.get("confidence", cur.get("confidence", 1.0))),
                "confirmed":    bool(m.get("confirmed", confirm_all or cur.get("confirmed", False))),
            }
        tpl.mappings = current
        confirmed_n = sum(1 for v in current.values() if v.get("confirmed"))
        tpl.status = "MAPPED" if confirmed_n > 0 else tpl.status
        # Move to VERIFIED if every mandatory canonical field for this kind is confirmed.
        required = REQUIRED_FOR_KIND.get(tpl.kind, set())
        if required and all(current.get(k, {}).get("confirmed") for k in required):
            tpl.status = "VERIFIED"
        await self.audit.record(
            session, company_id=tpl.company_id, actor_type="user", actor_id=actor_id,
            action="template.mapping_confirmed", resource=tpl.id,
            meta={"confirmed": confirmed_n, "status": tpl.status},
        )
        return tpl

    async def archive(self, session: AsyncSession, tpl: Template, *, actor_id: str) -> Template:
        tpl.status = "ARCHIVED"
        tpl.is_default = False
        await self.audit.record(
            session, company_id=tpl.company_id, actor_type="user", actor_id=actor_id,
            action="template.archived", resource=tpl.id,
        )
        return tpl

    async def make_version(
        self, session: AsyncSession, parent: Template, *,
        actor_id: str, storage_key: str, content: bytes, filename: str, mime: str,
    ) -> Template:
        analysis = await analyze(content, mime=mime, filename=filename)
        max_version = (await session.scalar(
            select(func.max(Template.version)).where(
                (Template.id == parent.id) | (Template.parent_template_id == parent.id),
            ),
        )) or parent.version
        new_tpl = Template(
            id=_id(), company_id=parent.company_id, name=parent.name,
            kind=parent.kind, format=analysis.format, body=storage_key, is_default=False,
            status="ANALYZED", original_filename=filename, file_hash=analysis.file_hash,
            language=analysis.language,
            version=int(max_version) + 1, parent_template_id=parent.parent_template_id or parent.id,
            detected_fields={"paragraphs": analysis.paragraphs[:60],
                             "placeholders": analysis.placeholders, "notes": analysis.notes},
            detected_tables=analysis.to_dict()["tables"],
            mappings=analysis.suggestions, confidence=analysis.confidence,
        )
        session.add(new_tpl)
        await self.audit.record(
            session, company_id=parent.company_id, actor_type="user", actor_id=actor_id,
            action="template.versioned", resource=new_tpl.id,
            meta={"parent": parent.id, "version": new_tpl.version},
        )
        return new_tpl


REQUIRED_FOR_KIND: dict[str, set[str]] = {
    "invoice":    {"company_name", "client_name", "invoice_number", "total"},
    "act":        {"company_name", "client_name"},
    "nakladnaya": {"company_name", "client_name", "items"},
    "contract":   {"company_name", "client_name"},
    "proposal":   {"company_name", "client_name", "total"},
}
