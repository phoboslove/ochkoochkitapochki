"""Plan CRUD — pricing/limits editable without a deploy. Plans are never
hard-deleted (existing subscriptions reference them by FK); DELETE
soft-disables via is_active instead."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, require_platform_admin
from app.db.models import Plan
from app.services.audit.logger import AuditLogger

router = APIRouter()
audit = AuditLogger()


def _serialize(p: Plan) -> dict:
    return {
        "id": p.id, "code": p.code, "name": p.name,
        "price_amount": float(p.price_amount), "price_currency": p.price_currency,
        "billing_period": p.billing_period,
        "limit_documents_per_month": p.limit_documents_per_month,
        "limit_users": p.limit_users, "limit_templates": p.limit_templates,
        "allowed_integrations": p.allowed_integrations,
        "is_active": p.is_active, "sort_order": p.sort_order,
    }


@router.get("/plans")
async def list_plans(
    _admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await session.scalars(select(Plan).order_by(Plan.sort_order))
    return [_serialize(p) for p in rows]


class PlanIn(BaseModel):
    code: str
    name: str
    price_amount: Decimal = Decimal(0)
    price_currency: str = "KZT"
    billing_period: str = "month"
    limit_documents_per_month: int
    limit_users: int
    limit_templates: int
    allowed_integrations: list[str] | None = None
    sort_order: int = 0


@router.post("/plans")
async def create_plan(
    body: PlanIn,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if await session.scalar(select(Plan).where(Plan.code == body.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"plan code {body.code!r} already exists")
    plan = Plan(
        id=f"plan_{uuid.uuid4().hex[:10]}", code=body.code, name=body.name,
        price_amount=body.price_amount, price_currency=body.price_currency,
        billing_period=body.billing_period,
        limit_documents_per_month=body.limit_documents_per_month,
        limit_users=body.limit_users, limit_templates=body.limit_templates,
        allowed_integrations=body.allowed_integrations, is_active=True,
        sort_order=body.sort_order,
    )
    session.add(plan)
    await audit.record(
        session, company_id="c_platform", actor_type="platform_admin", actor_id=admin.id,
        action="admin.plan_created", meta={"code": body.code},
    )
    await session.commit()
    return _serialize(plan)


class PlanUpdateIn(BaseModel):
    name: str | None = None
    price_amount: Decimal | None = None
    price_currency: str | None = None
    billing_period: str | None = None
    limit_documents_per_month: int | None = None
    limit_users: int | None = None
    limit_templates: int | None = None
    allowed_integrations: list[str] | None = None
    is_active: bool | None = None
    sort_order: int | None = None


@router.patch("/plans/{plan_id}")
async def update_plan(
    plan_id: str, body: PlanUpdateIn,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    plan = await session.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(plan, k, v)
    plan.updated_at = datetime.utcnow()
    await audit.record(
        session, company_id="c_platform", actor_type="platform_admin", actor_id=admin.id,
        action="admin.plan_updated", meta={"plan_id": plan_id, "changes": {k: str(v) for k, v in changes.items()}},
    )
    await session.commit()
    return _serialize(plan)


@router.delete("/plans/{plan_id}")
async def disable_plan(
    plan_id: str,
    admin: CurrentUser = Depends(require_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    plan = await session.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plan not found")
    plan.is_active = False
    await audit.record(
        session, company_id="c_platform", actor_type="platform_admin", actor_id=admin.id,
        action="admin.plan_disabled", meta={"plan_id": plan_id},
    )
    await session.commit()
    return {"id": plan.id, "is_active": plan.is_active}
