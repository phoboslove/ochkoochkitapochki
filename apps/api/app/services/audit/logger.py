"""DB-backed audit logger."""
from __future__ import annotations

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


class AuditLogger:
    async def record(
        self,
        session: AsyncSession,
        *,
        company_id: str,
        actor_type: str,
        action: str,
        resource: str | None = None,
        actor_id: str | None = None,
        meta: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            company_id=company_id, actor_type=actor_type, actor_id=actor_id,
            action=action, resource=resource, meta=meta or {},
        )
        session.add(entry)
        await session.flush()
        return entry

    async def list(self, session: AsyncSession, company_id: str, limit: int = 100) -> list[AuditLog]:
        rows = await session.scalars(
            select(AuditLog).where(AuditLog.company_id == company_id)
            .order_by(desc(AuditLog.at)).limit(limit),
        )
        return list(rows)
