"""Inbound webhook endpoints. Demo simulator + provider-specific endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.services.ai.orchestrator import AIOrchestrator
from app.services.audit.logger import AuditLogger
from app.services.integrations.whatsapp import build_whatsapp_provider

router = APIRouter()
orchestrator = AIOrchestrator()
audit = AuditLogger()


class WhatsAppSimIn(BaseModel):
    from_phone: str = "+7 700 000 0000"
    text: str


@router.post("/whatsapp/sim")
async def whatsapp_sim(
    body: WhatsAppSimIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await audit.record(
        session, company_id=user.company_id, actor_type="system",
        action="whatsapp.inbound", meta={"from": body.from_phone, "text": body.text},
    )
    result = await orchestrator.handle_message(
        session, company_id=user.company_id, actor_id=f"whatsapp:{body.from_phone}",
        conversation_id=None, message=body.text,
    )
    await session.commit()
    return {"received": True, **result}


@router.post("/whatsapp/{company_id}")
async def whatsapp_provider_inbound(
    company_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Production inbound webhook — provider posts to /webhooks/whatsapp/{company_id}."""
    from fastapi import HTTPException
    import json as _json
    raw = await request.body()
    provider = await build_whatsapp_provider(session, company_id)
    if hasattr(provider, "verify_signature"):
        sig = request.headers.get("x-hub-signature-256")
        if not provider.verify_signature(raw, sig):  # type: ignore[attr-defined]
            raise HTTPException(401, "invalid signature")
    payload = _json.loads(raw or b"{}") if request.headers.get("content-type", "").startswith("application/json") \
        else dict(await request.form())
    messages = await provider.parse_inbound(payload)
    for m in messages:
        text = (m.get("text") or "").strip()
        if not text:
            continue
        await orchestrator.handle_message(
            session, company_id=company_id, actor_id=f"whatsapp:{m.get('from')}",
            conversation_id=None, message=text,
        )
    await session.commit()
    return {"received": len(messages)}


@router.get("/whatsapp/{company_id}")
async def whatsapp_verify(company_id: str, request: Request, session: AsyncSession = Depends(get_session)) -> str:
    provider = await build_whatsapp_provider(session, company_id)
    challenge = await provider.verify_webhook(dict(request.query_params))
    return challenge or ""
