from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.db.models import AuditLog

router = APIRouter()


def _serialize(r: AuditLog) -> dict:
    return {"id": r.id, "at": r.at.isoformat(), "actor_type": r.actor_type, "actor_id": r.actor_id,
            "action": r.action, "resource": r.resource, "meta": r.meta}


@router.get("")
async def list_logs(
    resource: str | None = None,
    limit: int = 200,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    q = select(AuditLog).where(AuditLog.company_id == user.company_id)
    if resource:
        q = q.where(AuditLog.resource == resource)
    rows = await session.scalars(q.order_by(desc(AuditLog.at)).limit(limit))
    return [_serialize(r) for r in rows]
