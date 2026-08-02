"""Auth endpoints — register company+owner, login, current user."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.core.ratelimit import rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import Company, User

router = APIRouter()

# bcrypt verify is intentionally slow; 5/min/IP stops scripted brute-force
# while leaving a real operator who fat-fingers a password headroom.
_login_limit    = rate_limit("auth.login",    limit=5,  window_s=60)
_register_limit = rate_limit("auth.register", limit=3,  window_s=300)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RegisterIn(BaseModel):
    company_name: str
    email: EmailStr
    password: str
    name: str | None = None
    bin: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _token(user: User) -> str:
    return create_access_token(sub=user.id, claims={"company_id": user.company_id, "role": user.role})


def _user_dict(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "company_id": u.company_id}


@router.post("/register", response_model=TokenOut,
             dependencies=[Depends(_register_limit)])
async def register(body: RegisterIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    if await session.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "email already in use")
    company = Company(id=f"c_{uuid.uuid4().hex[:10]}", name=body.company_name, bin=body.bin, settings={})
    user = User(
        id=f"u_{uuid.uuid4().hex[:10]}", company_id=company.id, email=body.email,
        name=body.name, role="OWNER", password_hash=hash_password(body.password),
    )
    session.add_all([company, user])
    await session.flush()

    # First-time-user experience: seed verified commercial RU templates so
    # the very first /documents/generate call returns a real DOCX, not an
    # HTML fallback. Best-effort — registration must not fail because of
    # template seeding hiccups (e.g. storage briefly unavailable).
    try:
        from app.services.templates.commercial_seed import install_for_tenant
        await install_for_tenant(session, company_id=company.id)
    except Exception:  # noqa: BLE001
        from app.core.logging import log
        log.exception("commercial_seed_failed", company_id=company.id)

    await session.commit()
    return TokenOut(access_token=_token(user), user=_user_dict(user))


@router.post("/login", response_model=TokenOut,
             dependencies=[Depends(_login_limit)])
async def login(body: LoginIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    user = await session.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash) or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return TokenOut(access_token=_token(user), user=_user_dict(user))


@router.get("/me")
async def me(current: CurrentUser = Depends(get_current_user)) -> dict:
    return {"id": current.id, "email": current.email, "role": current.role, "company_id": current.company_id}
