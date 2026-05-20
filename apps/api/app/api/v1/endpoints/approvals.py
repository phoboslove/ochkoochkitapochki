from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user, require_admin
from app.services.approvals.service import ApprovalService

router = APIRouter()
service = ApprovalService()


def _serialize(a) -> dict:
    return {
        "id": a.id, "resource_type": a.resource_type, "resource_id": a.resource_id,
        "action": a.action, "summary": a.summary, "status": a.status,
        "requested_by": a.requested_by, "decided_by": a.decided_by,
        "created_at": a.created_at.isoformat(), "payload": a.payload,
    }


class DecideIn(BaseModel):
    approve: bool


@router.get("")
async def list_approvals(
    status: str | None = None,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await service.list(session, user.company_id, status=status)
    return [_serialize(a) for a in rows]


@router.post("/{approval_id}/decide")
async def decide(
    approval_id: str, body: DecideIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    approval = await service.get(session, approval_id)
    if not approval or approval.company_id != user.company_id:
        raise HTTPException(404, "approval not found")
    approval = await service.decide(session, approval_id, approve=body.approve, decided_by=user.id)
    await session.commit()
    return _serialize(approval)
