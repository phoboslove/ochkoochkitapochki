from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user, require_admin
from app.core.security import create_access_token
from app.db.models import User
from app.services.audit.logger import AuditLogger
from app.services.invitations.service import InvitationService

router = APIRouter()
service = InvitationService()
audit = AuditLogger()


class InviteIn(BaseModel):
    email: EmailStr
    role: str = "MEMBER"


class AcceptIn(BaseModel):
    token: str
    password: str
    name: str | None = None


def _serialize(i) -> dict:
    return {"id": i.id, "email": i.email, "role": i.role, "status": i.status,
            "token": i.token, "invited_by": i.invited_by,
            "expires_at": i.expires_at.isoformat(), "created_at": i.created_at.isoformat()}


@router.get("")
async def list_invites(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    invites = await service.list(session, user.company_id)
    members = list(await session.scalars(
        select(User).where(User.company_id == user.company_id),
    ))
    return {
        "members": [{"id": m.id, "email": m.email, "name": m.name, "role": m.role, "active": m.active}
                    for m in members],
        "invites": [_serialize(i) for i in invites],
    }


@router.post("")
async def invite(
    body: InviteIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.services.limits.usage import assert_can_invite_seat
    await assert_can_invite_seat(session, user.company_id)
    try:
        inv = await service.invite(
            session, company_id=user.company_id, email=body.email, role=body.role, invited_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    await audit.record(
        session, company_id=user.company_id, actor_type="user", actor_id=user.id,
        action="invite.created", resource=inv.id, meta={"email": body.email, "role": body.role},
    )
    await session.commit()
    return _serialize(inv)


@router.post("/{invite_id}/revoke")
async def revoke(
    invite_id: str,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    inv = await service.revoke(session, user.company_id, invite_id)
    if not inv:
        raise HTTPException(404, "invite not found or not pending")
    await audit.record(session, company_id=user.company_id, actor_type="user", actor_id=user.id,
                       action="invite.revoked", resource=inv.id)
    await session.commit()
    return _serialize(inv)


@router.post("/accept")
async def accept(body: AcceptIn, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        u = await service.accept(session, token=body.token, name=body.name, password=body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await audit.record(session, company_id=u.company_id, actor_type="user", actor_id=u.id,
                       action="invite.accepted", meta={"role": u.role})
    await session.commit()
    token = create_access_token(sub=u.id, claims={"company_id": u.company_id, "role": u.role})
    return {"access_token": token, "user": {"id": u.id, "email": u.email, "role": u.role}}


class UpdateRoleIn(BaseModel):
    role: str


@router.patch("/members/{user_id}/role")
async def update_role(
    user_id: str, body: UpdateRoleIn,
    actor: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    target = await session.get(User, user_id)
    if not target or target.company_id != actor.company_id:
        raise HTTPException(404, "member not found")
    if target.role == "OWNER" and body.role != "OWNER":
        raise HTTPException(400, "cannot demote the OWNER")
    target.role = body.role
    await audit.record(session, company_id=actor.company_id, actor_type="user", actor_id=actor.id,
                       action="member.role_changed", resource=target.id, meta={"role": body.role})
    await session.commit()
    return {"id": target.id, "role": target.role}
