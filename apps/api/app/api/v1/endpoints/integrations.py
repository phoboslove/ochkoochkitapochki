"""Integration management — list, connect (with provider config), disconnect, test."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user, require_admin
from app.db.models import Integration

router = APIRouter()


_KNOWN = ["whatsapp", "telegram", "bitrix", "amocrm", "kaspi", "ozon", "gsheets", "gmail", "gdrive", "1c"]


class ConnectIn(BaseModel):
    config: dict = {}
    secrets: dict = {}


def _serialize(i: Integration) -> dict:
    return {"id": i.id, "provider": i.provider, "status": i.status, "config": i.config}


@router.get("")
async def list_integrations(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = list(await session.scalars(
        select(Integration).where(Integration.company_id == user.company_id),
    ))
    by_provider = {r.provider: r for r in rows}
    out = []
    for p in _KNOWN:
        i = by_provider.get(p)
        out.append(_serialize(i) if i else {"id": None, "provider": p, "status": "disconnected", "config": {}})
    return out


@router.post("/{provider}/connect")
async def connect(
    provider: str, body: ConnectIn,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if provider not in _KNOWN:
        raise HTTPException(400, "unknown provider")
    from app.db.models import Company
    from app.services.plans.gate import integration_allowed
    company = await session.get(Company, user.company_id)
    if not integration_allowed(company.plan if company else "free", provider):
        raise HTTPException(402, f"{provider} requires a higher plan")
    integration = await session.scalar(
        select(Integration).where(Integration.company_id == user.company_id, Integration.provider == provider),
    )
    if not integration:
        integration = Integration(
            id=f"int_{uuid.uuid4().hex[:10]}", company_id=user.company_id, provider=provider,
        )
        session.add(integration)
    integration.config = body.config
    integration.secrets = body.secrets
    integration.status = "connected"
    await session.commit()
    return _serialize(integration)


@router.post("/{provider}/disconnect")
async def disconnect(
    provider: str,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    integration = await session.scalar(
        select(Integration).where(Integration.company_id == user.company_id, Integration.provider == provider),
    )
    if not integration:
        raise HTTPException(404, "not connected")
    integration.status = "disconnected"
    await session.commit()
    return _serialize(integration)


@router.post("/{provider}/test")
async def test(
    provider: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if provider == "whatsapp":
        from app.services.integrations.whatsapp import WhatsAppMessage, build_whatsapp_provider
        prov = await build_whatsapp_provider(session, user.company_id)
        result = await prov.send(WhatsAppMessage(to="+0", text="Buchuchet test ping"))
        return {"provider": provider, "ok": True, "result": result}
    return {"provider": provider, "ok": True, "note": "test stub"}
