"""AI conversations — list, restore history, rename, archive.

All persisted in Postgres already via the orchestrator. These endpoints surface
them as a real operational copilot history (not a transient chat).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.db.models import Conversation, Message

router = APIRouter()


def _summary(c: Conversation, last: str | None, count: int) -> dict:
    return {"id": c.id, "title": c.title or _auto_title(last) or "New conversation",
            "created_at": c.created_at.isoformat(), "message_count": count,
            "user_id": c.user_id}


def _auto_title(text: str | None) -> str | None:
    if not text: return None
    t = text.strip().split("\n", 1)[0]
    return t[:60] + ("…" if len(t) > 60 else "")


@router.get("")
async def list_conversations(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = 30,
) -> list[dict]:
    rows = list(await session.scalars(
        select(Conversation).where(Conversation.company_id == user.company_id)
            .order_by(desc(Conversation.created_at)).limit(limit),
    ))
    out: list[dict] = []
    for c in rows:
        # First user message → fallback title.
        first = await session.scalar(
            select(Message).where(Message.conversation_id == c.id, Message.role == "user")
                .order_by(Message.id).limit(1),
        )
        count = (await session.scalar(
            select(func.count(Message.id)).where(Message.conversation_id == c.id),
        )) or 0
        out.append(_summary(c, first.content if first else None, count))
    return out


@router.get("/{conv_id}")
async def get_conversation(
    conv_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    conv = await session.get(Conversation, conv_id)
    if not conv or conv.company_id != user.company_id:
        raise HTTPException(404, "conversation not found")
    rows = list(await session.scalars(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.id),
    ))
    msgs = [
        {
            "id": m.id, "role": m.role, "content": m.content,
            "at": m.created_at.isoformat(),
            "tool_calls": m.tool_calls or [],
        } for m in rows if m.role in ("user", "assistant")
    ]
    first_user = next((m for m in rows if m.role == "user"), None)
    return {
        "id": conv.id, "title": conv.title or _auto_title(first_user.content if first_user else None),
        "created_at": conv.created_at.isoformat(),
        "messages": msgs,
    }


class RenameIn(BaseModel):
    title: str


@router.patch("/{conv_id}")
async def rename_conversation(
    conv_id: str, body: RenameIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    conv = await session.get(Conversation, conv_id)
    if not conv or conv.company_id != user.company_id:
        raise HTTPException(404, "conversation not found")
    conv.title = body.title.strip()[:200]
    await session.commit()
    return {"id": conv.id, "title": conv.title}


@router.delete("/{conv_id}")
async def delete_conversation(
    conv_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    conv = await session.get(Conversation, conv_id)
    if not conv or conv.company_id != user.company_id:
        raise HTTPException(404, "conversation not found")
    # Hard delete messages, then conversation.
    await session.execute(Message.__table__.delete().where(Message.conversation_id == conv_id))
    await session.delete(conv)
    await session.commit()
    return {"deleted": True}
