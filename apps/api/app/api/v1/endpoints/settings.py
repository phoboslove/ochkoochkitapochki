"""Typed settings endpoints — one PATCH per section, validated by Pydantic."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user, require_admin
from app.services.context import ALL_SECTIONS, ContextService

router = APIRouter()
service = ContextService()


@router.get("")
async def get_settings(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ctx = await service.load(session, user.company_id)
    return ctx.model_dump()


class SectionPatch(BaseModel):
    data: dict


@router.patch("/{section}")
async def patch_section(
    section: str, body: SectionPatch,
    user: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if section not in ALL_SECTIONS:
        raise HTTPException(404, f"unknown section: {section}")
    try:
        ctx = await service.patch_section(
            session, company_id=user.company_id, section=section,
            data=body.data, actor_id=user.id,
        )
    except Exception as exc:  # pydantic ValidationError, etc.
        raise HTTPException(400, str(exc))
    await session.commit()
    return ctx.model_dump()
