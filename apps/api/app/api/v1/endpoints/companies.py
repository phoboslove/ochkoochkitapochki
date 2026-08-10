"""Company profile + memory + branding endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user, require_admin
from app.db.models import Company
from app.services.companies.memory import CompanyMemory
from app.services.storage import get_storage

router = APIRouter()
memory = CompanyMemory()


class UpdateCompanyIn(BaseModel):
    name: str | None = None
    bin: str | None = None
    tax_mode: str | None = None
    country_code: str | None = None


class UpdateSettingsIn(BaseModel):
    settings: dict


async def _onboarding_state(session: AsyncSession, company_id: str) -> dict:
    """Compute checklist state from real DB facts — never trust a stored flag alone."""
    from sqlalchemy import select, func
    from app.db.models import Company, Integration, Invoice, Template, User
    company = await session.get(Company, company_id)
    has_logo  = bool(company and company.logo_key)
    has_users = (await session.scalar(
        select(func.count(User.id)).where(User.company_id == company_id),
    )) or 0
    has_inv = await session.scalar(
        select(func.count(Invoice.id)).where(Invoice.company_id == company_id),
    )
    has_tpl = await session.scalar(
        select(func.count(Template.id)).where(Template.company_id == company_id, Template.format == "docx"),
    )
    has_wa = await session.scalar(
        select(Integration).where(
            Integration.company_id == company_id,
            Integration.provider == "whatsapp",
            Integration.status == "connected",
        ),
    )
    steps = [
        {"key": "organization", "label": "Create organization",   "done": True},
        {"key": "branding",     "label": "Upload logo",           "done": has_logo},
        {"key": "template",     "label": "Add invoice template",  "done": (has_tpl or 0) > 0, "optional": True},
        {"key": "whatsapp",     "label": "Connect WhatsApp",      "done": bool(has_wa), "optional": True},
        {"key": "first_invoice","label": "Create first invoice",  "done": (has_inv or 0) > 0},
        {"key": "team",         "label": "Invite a teammate",     "done": (has_users or 0) > 1, "optional": True},
    ]
    required_done = all(s["done"] for s in steps if not s.get("optional"))
    return {"steps": steps, "completed": bool(company and company.onboarded) or required_done}


@router.get("/onboarding")
async def onboarding(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _onboarding_state(session, user.company_id)


@router.post("/onboarding/complete")
async def complete_onboarding(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    company = await session.get(Company, user.company_id)
    if not company:
        raise HTTPException(404, "company not found")
    company.onboarded = True
    await session.commit()
    return {"completed": True}


@router.post("/seed-demo")
async def seed_demo_data(
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    from app.services.demo.seeder import seed_demo
    result = await seed_demo(session, company_id=user.company_id, actor_id=user.id)
    await session.commit()
    return result


@router.get("/analytics/usage")
async def usage_analytics(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Aggregate audit logs into a usage snapshot (no extra table needed)."""
    from sqlalchemy import select, func
    from datetime import datetime, timedelta
    from app.db.models import AuditLog
    cutoff = datetime.utcnow() - timedelta(days=30)
    rows = await session.execute(
        select(AuditLog.action, func.count(AuditLog.id)).where(
            AuditLog.company_id == user.company_id, AuditLog.at >= cutoff,
        ).group_by(AuditLog.action),
    )
    counts = {action: n for action, n in rows.all()}

    def total(prefix: str) -> int:
        return sum(v for k, v in counts.items() if k.startswith(prefix))

    from app.services.billing.repo import get_subscription_and_plan
    try:
        _sub, plan = await get_subscription_and_plan(session, user.company_id)
        plan_block = {
            "name": plan.name,
            "limits": {
                "documents_per_month": plan.limit_documents_per_month,
                "seats":               plan.limit_users,
                "templates":           plan.limit_templates,
            },
        }
    except LookupError:
        plan_block = None
    return {
        "window_days": 30,
        "ai_tool_invocations": counts.get("ai.tool_invoked", 0),
        "ai_tool_denied":      counts.get("ai.tool_denied", 0),
        "approvals_decided":   counts.get("approval.decide", 0),
        "approvals_requested": counts.get("approval.request", 0),
        "invoices_created":    counts.get("invoice.create_draft", 0),
        "invoices_sent":       counts.get("whatsapp.send_pdf", 0),
        "documents_uploaded":  counts.get("document.upload", 0),
        "workflow_failures":   total("workflow.run_failed"),
        "by_action": counts,
        "plan": plan_block,
    }


@router.get("/me")
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    company = await session.get(Company, user.company_id)
    if not company:
        raise HTTPException(404, "company not found")
    return {
        "id": company.id, "name": company.name, "bin": company.bin,
        "tax_mode": company.tax_mode, "country_code": company.country_code,
        "settings": company.settings,
        "plan": company.plan, "onboarded": company.onboarded,
        "logo_url": get_storage().presign_get(company.logo_key, expires_in=3600) if company.logo_key else None,
    }


@router.get("/memory")
async def memory_dump(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await memory.load(session, user.company_id)


@router.patch("/me")
async def update_company(
    body: UpdateCompanyIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    company = await session.get(Company, user.company_id)
    if not company:
        raise HTTPException(404, "company not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(company, k, v)
    await session.commit()
    return {"id": company.id, "name": company.name}


@router.patch("/settings")
async def update_settings(
    body: UpdateSettingsIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    merged = await memory.update_settings(session, user.company_id, body.settings)
    await session.commit()
    return {"settings": merged}


@router.post("/branding/logo")
async def upload_logo(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "image required")
    company = await session.get(Company, user.company_id)
    if not company:
        raise HTTPException(404, "company not found")
    key = f"{company.id}/branding/logo.{(file.filename or 'logo').rsplit('.', 1)[-1].lower()}"
    body = await file.read()
    get_storage().put(key, body, content_type=file.content_type)
    company.logo_key = key
    company.settings = {**(company.settings or {}), "branding": {**((company.settings or {}).get("branding") or {}), "logo_key": key}}
    await session.commit()
    return {"logo_key": key, "logo_url": get_storage().presign_get(key, expires_in=3600)}
