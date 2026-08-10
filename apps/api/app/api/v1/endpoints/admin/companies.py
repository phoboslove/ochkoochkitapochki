"""Platform admin — company lifecycle: list/search, detail, create,
per-company users, subscription actions. Every mutation is audited with
actor_type="platform_admin" via the existing AuditLogger — same mechanism
as tenant audit trails, just a different actor_type.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, require_platform_admin
from app.core.security import hash_password
from app.db.models import AuditLog, Company, Payment, Plan, Subscription, User
from app.services.audit.logger import AuditLogger
from app.services.billing.repo import get_plan_by_code, get_subscription_and_plan
from app.services.billing.status import refresh_status
from app.services.billing.usage import get_current_usage

router = APIRouter()
audit = AuditLogger()

_PLATFORM_COMPANY_ID = "c_platform"


# ── List / search ────────────────────────────────────────────────────────

@router.get("/companies")
async def list_companies(
    status_filter: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(Company, Subscription, Plan).join(
        Subscription, Subscription.company_id == Company.id, isouter=True,
    ).join(Plan, Plan.id == Subscription.plan_id, isouter=True).where(
        Company.id != _PLATFORM_COMPANY_ID,
    )
    if status_filter:
        stmt = stmt.where(Subscription.status == status_filter)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Company.name.ilike(like), Company.bin.ilike(like)))
    stmt = stmt.order_by(Company.created_at.desc()).limit(limit).offset(offset)

    rows = (await session.execute(stmt)).all()
    items = []
    for company, sub, plan in rows:
        users_count = await session.scalar(
            select(func.count(User.id)).where(User.company_id == company.id, User.active == True),  # noqa: E712
        )
        items.append({
            "id": company.id, "name": company.name, "bin": company.bin,
            "created_at": company.created_at.isoformat(),
            "users_count": users_count or 0,
            "subscription": {
                "status": sub.status if sub else None,
                "period_end": sub.period_end.isoformat() if sub else None,
                "plan_code": plan.code if plan else None,
                "plan_name": plan.name if plan else None,
            } if sub else None,
        })
    total = await session.scalar(
        select(func.count(Company.id)).where(Company.id != _PLATFORM_COMPANY_ID),
    ) or 0
    return {"items": items, "total": total}


# ── Detail ────────────────────────────────────────────────────────────────

@router.get("/companies/{company_id}")
async def company_detail(
    company_id: str,
    _admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "company not found")

    try:
        subscription, plan = await get_subscription_and_plan(session, company_id)
        subscription = await refresh_status(session, subscription)
        used = await get_current_usage(session, company_id)
        sub_block = {
            "id": subscription.id, "status": subscription.status,
            "period_start": subscription.period_start.isoformat(),
            "period_end": subscription.period_end.isoformat(),
            "grace_period_days": subscription.grace_period_days,
            "renewal_method": subscription.renewal_method,
            "plan": {"id": plan.id, "code": plan.code, "name": plan.name,
                     "price_amount": float(plan.price_amount), "price_currency": plan.price_currency,
                     "limit_documents_per_month": plan.limit_documents_per_month,
                     "limit_users": plan.limit_users, "limit_templates": plan.limit_templates},
            "usage": {"documents_used": used, "documents_limit": plan.limit_documents_per_month},
        }
    except LookupError:
        sub_block = None

    users = list(await session.scalars(
        select(User).where(User.company_id == company_id).order_by(User.created_at),
    ))
    payments = list(await session.scalars(
        select(Payment).where(Payment.company_id == company_id).order_by(Payment.created_at.desc()).limit(50),
    ))

    # Usage by month — last 6 calendar months from the atomic counter.
    from app.db.models import UsageCounter
    usage_rows = list(await session.scalars(
        select(UsageCounter).where(UsageCounter.company_id == company_id)
        .order_by(UsageCounter.period.desc()).limit(6),
    ))

    audit_rows = list(await session.scalars(
        select(AuditLog).where(AuditLog.company_id == company_id)
        .order_by(AuditLog.at.desc()).limit(50),
    ))

    return {
        "company": {"id": company.id, "name": company.name, "bin": company.bin,
                    "country_code": company.country_code, "created_at": company.created_at.isoformat()},
        "subscription": sub_block,
        "users": [
            {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "active": u.active,
             "created_at": u.created_at.isoformat()}
            for u in users
        ],
        "payments": [
            {"id": p.id, "amount": float(p.amount), "currency": p.currency, "status": p.status,
             "method": p.method, "comment": p.comment, "paid_at": p.paid_at.isoformat() if p.paid_at else None,
             "created_at": p.created_at.isoformat()}
            for p in payments
        ],
        "usage_by_month": [
            {"period": r.period, "documents_count": r.documents_count} for r in usage_rows
        ],
        "audit_trail": [
            {"id": a.id, "actor_type": a.actor_type, "actor_id": a.actor_id, "action": a.action,
             "resource": a.resource, "meta": a.meta, "at": a.at.isoformat()}
            for a in audit_rows
        ],
    }


# ── Create company ───────────────────────────────────────────────────────

class CreateCompanyIn(BaseModel):
    company_name: str
    bin: str | None = None
    plan_code: str
    owner_email: EmailStr
    owner_name: str | None = None
    owner_password: str


@router.post("/companies")
async def create_company(
    body: CreateCompanyIn,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if await session.scalar(select(User).where(User.email == body.owner_email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "email already in use")
    plan = await get_plan_by_code(session, body.plan_code)
    if not plan:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown plan code: {body.plan_code!r}")

    company = Company(id=f"c_{uuid.uuid4().hex[:10]}", name=body.company_name, bin=body.bin, settings={})
    owner = User(
        id=f"u_{uuid.uuid4().hex[:10]}", company_id=company.id, email=body.owner_email,
        name=body.owner_name, role="OWNER", password_hash=hash_password(body.owner_password),
    )
    now = datetime.utcnow()
    subscription = Subscription(
        id=f"sub_{uuid.uuid4().hex[:12]}", company_id=company.id, plan_id=plan.id,
        status="trialing" if plan.code == "trial" else "active",
        period_start=now, period_end=now + timedelta(days=30 if plan.code == "trial" else 30),
        renewal_method="manual", grace_period_days=5,
    )
    session.add_all([company, owner, subscription])
    await audit.record(
        session, company_id=company.id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.company_created", meta={"plan_code": plan.code, "owner_email": body.owner_email},
    )
    await session.commit()
    return {"company_id": company.id, "owner_user_id": owner.id, "subscription_id": subscription.id}


# ── Users within a company ──────────────────────────────────────────────

class CreateUserIn(BaseModel):
    email: EmailStr
    name: str | None = None
    role: str = "MEMBER"
    password: str


@router.post("/companies/{company_id}/users")
async def create_company_user(
    company_id: str, body: CreateUserIn,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not await session.get(Company, company_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "company not found")
    if await session.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "email already in use")
    user = User(
        id=f"u_{uuid.uuid4().hex[:10]}", company_id=company_id, email=body.email,
        name=body.name, role=body.role, password_hash=hash_password(body.password),
    )
    session.add(user)
    await audit.record(
        session, company_id=company_id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.user_created", meta={"user_email": body.email, "role": body.role},
    )
    await session.commit()
    return {"id": user.id, "email": user.email}


@router.patch("/companies/{company_id}/users/{user_id}")
async def set_user_active(
    company_id: str, user_id: str, active: bool,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await session.get(User, user_id)
    if not user or user.company_id != company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    user.active = active
    await audit.record(
        session, company_id=company_id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.user_active_changed", meta={"user_id": user_id, "active": active},
    )
    await session.commit()
    return {"id": user.id, "active": user.active}


@router.post("/companies/{company_id}/users/{user_id}/reset-password")
async def reset_user_password(
    company_id: str, user_id: str,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await session.get(User, user_id)
    if not user or user.company_id != company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    new_password = secrets.token_urlsafe(12)
    user.password_hash = hash_password(new_password)
    await audit.record(
        session, company_id=company_id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.user_password_reset", meta={"user_id": user_id},
    )
    await session.commit()
    # Returned once — the only place this plaintext password ever exists
    # outside the admin's own clipboard; never logged.
    return {"id": user.id, "temporary_password": new_password}


# ── Subscription actions ────────────────────────────────────────────────

class ChangePlanIn(BaseModel):
    plan_code: str


@router.post("/companies/{company_id}/subscription/change-plan")
async def change_plan(
    company_id: str, body: ChangePlanIn,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    subscription, old_plan = await get_subscription_and_plan(session, company_id)
    new_plan = await get_plan_by_code(session, body.plan_code)
    if not new_plan:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown plan code: {body.plan_code!r}")
    subscription.plan_id = new_plan.id
    await audit.record(
        session, company_id=company_id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.plan_changed", meta={"from": old_plan.code, "to": new_plan.code},
    )
    await session.commit()
    return {"plan_code": new_plan.code}


class ExtendIn(BaseModel):
    days: int = 30


@router.post("/companies/{company_id}/subscription/extend")
async def extend_subscription(
    company_id: str, body: ExtendIn,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    subscription, _plan = await get_subscription_and_plan(session, company_id)
    # Extend from whichever is later — "now" (if already expired) or the
    # current period_end (if renewing early) — so early renewal doesn't
    # forfeit remaining paid time.
    base = max(subscription.period_end, datetime.utcnow())
    subscription.period_end = base + timedelta(days=body.days)
    subscription.status = "active"
    subscription.suspended_at = None
    await audit.record(
        session, company_id=company_id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.subscription_extended",
        meta={"days": body.days, "new_period_end": subscription.period_end.isoformat()},
    )
    await session.commit()
    return {"period_end": subscription.period_end.isoformat(), "status": subscription.status}


@router.post("/companies/{company_id}/subscription/suspend")
async def suspend_subscription(
    company_id: str,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    subscription, _plan = await get_subscription_and_plan(session, company_id)
    subscription.status = "suspended"
    subscription.suspended_at = datetime.utcnow()
    await audit.record(
        session, company_id=company_id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.subscription_suspended", meta={},
    )
    await session.commit()
    return {"status": subscription.status}


@router.post("/companies/{company_id}/subscription/reactivate")
async def reactivate_subscription(
    company_id: str,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    subscription, _plan = await get_subscription_and_plan(session, company_id)
    subscription.status = "active"
    subscription.suspended_at = None
    if subscription.period_end <= datetime.utcnow():
        subscription.period_end = datetime.utcnow() + timedelta(days=30)
    await audit.record(
        session, company_id=company_id, actor_type="platform_admin", actor_id=admin.id,
        action="admin.subscription_reactivated",
        meta={"period_end": subscription.period_end.isoformat()},
    )
    await session.commit()
    return {"status": subscription.status, "period_end": subscription.period_end.isoformat()}
