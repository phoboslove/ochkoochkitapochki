"""Auth endpoints — register company+owner, login, current user."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
_verify_limit   = rate_limit("auth.verify",   limit=10, window_s=300)
_resend_limit   = rate_limit("auth.resend_code", limit=5, window_s=300)


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    turnstile_token: str | None = None


class RegisterIn(BaseModel):
    company_name: str
    email: EmailStr
    password: str
    name: str | None = None
    bin: str | None = None
    turnstile_token: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class RegisterOut(BaseModel):
    status: str = "verification_required"
    email: str


class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str


class ResendCodeIn(BaseModel):
    email: EmailStr


class EmailNotVerifiedError(Exception):
    """Correct credentials, but the account is still pending its email code.
    Caught by the global handler in main.py -> 403 with a distinct `error`
    field so the frontend can route to the verification screen instead of
    showing a generic "wrong password" message."""
    def __init__(self, email: str):
        self.email = email


def _verification_required() -> bool:
    """Off by default — beta customers are onboarded by hand today, and a
    code gate only adds friction with no real bot-fighting benefit while
    RESEND_API_KEY isn't configured (codes would only ever reach the server
    log, locking real users out). Flip on once Resend is wired up."""
    return os.environ.get("REQUIRE_EMAIL_VERIFICATION", "false").lower() in ("1", "true", "yes")


def _token(user: User) -> str:
    return create_access_token(sub=user.id, claims={"company_id": user.company_id, "role": user.role})


def _user_dict(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "company_id": u.company_id}


@router.post("/register", response_model=TokenOut | RegisterOut,
             dependencies=[Depends(_register_limit)])
async def register(body: RegisterIn, request: Request, session: AsyncSession = Depends(get_session)) -> TokenOut | RegisterOut:
    from app.core.ratelimit import _client_key
    from app.services.auth.turnstile import verify_turnstile
    if not await verify_turnstile(body.turnstile_token, _client_key(request)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bot check failed — please retry")
    if await session.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "email already in use")
    require_verification = _verification_required()
    company = Company(id=f"c_{uuid.uuid4().hex[:10]}", name=body.company_name, bin=body.bin, settings={})
    user = User(
        id=f"u_{uuid.uuid4().hex[:10]}", company_id=company.id, email=body.email,
        name=body.name, role="OWNER", password_hash=hash_password(body.password),
        email_verified=not require_verification,
    )
    session.add_all([company, user])
    await session.flush()

    # Every company must have a subscription from the moment it exists —
    # enforcement (app/services/billing/enforce.py) assumes this and treats
    # a missing subscription as a data-integrity bug, not a normal state.
    from app.services.billing.repo import create_trial_subscription
    await create_trial_subscription(session, company.id)

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

    try:
        from app.services.templates.kz_legal_seed import install_for_tenant as install_kz_legal
        await install_kz_legal(session, company_id=company.id)
    except Exception:  # noqa: BLE001
        from app.core.logging import log
        log.exception("kz_legal_seed_failed", company_id=company.id)

    await session.commit()

    if not require_verification:
        return TokenOut(access_token=_token(user), user=_user_dict(user))

    # Best-effort too: the account already exists and can request a resend
    # from the verification screen if this particular send fails (transient
    # provider outage). We don't want a flaky mail provider to roll back an
    # otherwise-successful signup.
    try:
        from app.services.auth.verification import issue_code
        from app.services.email.service import get_mailer, render_verification_code
        code = await issue_code(session, user.id)
        await session.commit()
        await get_mailer().send(render_verification_code(email=user.email, code=code))
    except Exception:  # noqa: BLE001
        from app.core.logging import log
        log.exception("verification_email_failed", user_id=user.id)

    return RegisterOut(email=user.email)


@router.post("/verify-email", response_model=TokenOut,
             dependencies=[Depends(_verify_limit)])
async def verify_email(body: VerifyEmailIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    user = await session.scalar(select(User).where(User.email == body.email))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    if not user.email_verified:
        from app.services.auth.verification import CodeInvalid, verify_code
        try:
            await verify_code(session, user.id, body.code)
        except CodeInvalid as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        user.email_verified = True
        await session.commit()
    return TokenOut(access_token=_token(user), user=_user_dict(user))


@router.post("/resend-code", dependencies=[Depends(_resend_limit)])
async def resend_code(body: ResendCodeIn, session: AsyncSession = Depends(get_session)) -> dict:
    # Deliberately doesn't require the password: this is a low-stakes resend
    # of an OTP the recipient still can't use without inbox access, and
    # adding a password prompt to a screen whose whole point is "I lost my
    # code" is worse UX for negligible security gain. To avoid leaking which
    # emails are registered, every branch below returns the same generic
    # {"status": "sent"} — only the 429 (rate limit) is observably different,
    # same as any other endpoint's rate limiting.
    user = await session.scalar(select(User).where(User.email == body.email))
    if user and not user.email_verified:
        from app.services.auth.verification import CodeResendTooSoon, issue_code
        try:
            code = await issue_code(session, user.id)
        except CodeResendTooSoon as exc:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Повторная отправка возможна через {exc.retry_after_s} сек.",
                headers={"Retry-After": str(exc.retry_after_s)},
            )
        await session.commit()
        from app.services.email.service import get_mailer, render_verification_code
        await get_mailer().send(render_verification_code(email=user.email, code=code))
    return {"status": "sent"}


@router.post("/login", response_model=TokenOut,
             dependencies=[Depends(_login_limit)])
async def login(body: LoginIn, request: Request, session: AsyncSession = Depends(get_session)) -> TokenOut:
    from app.core.ratelimit import _client_key
    from app.services.auth.turnstile import verify_turnstile
    if not await verify_turnstile(body.turnstile_token, _client_key(request)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "bot check failed — please retry")
    user = await session.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash) or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if _verification_required() and not user.email_verified:
        raise EmailNotVerifiedError(user.email)
    return TokenOut(access_token=_token(user), user=_user_dict(user))


@router.get("/me")
async def me(current: CurrentUser = Depends(get_current_user)) -> dict:
    return {"id": current.id, "email": current.email, "name": current.name,
            "role": current.role, "company_id": current.company_id,
            "is_platform_admin": current.is_platform_admin}
