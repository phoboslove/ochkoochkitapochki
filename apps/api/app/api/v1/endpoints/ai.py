from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.services.ai.orchestrator import AIOrchestrator

router = APIRouter()
orchestrator = AIOrchestrator()


@router.get("/tools")
async def list_tools(_user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    """Expose tool manifest (with danger + min_role) so the UI can label AI actions."""
    return orchestrator.tools.manifest()


class ChatIn(BaseModel):
    conversation_id: str | None = None
    message: str


class ChatOut(BaseModel):
    conversation_id: str
    reply: str
    tool_calls: list[dict] = []


@router.post("/chat", response_model=ChatOut)
async def chat(
    body: ChatIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChatOut:
    result = await orchestrator.handle_message(
        session, company_id=user.company_id, actor_id=user.id,
        conversation_id=body.conversation_id, message=body.message,
        actor_role=user.role,
    )
    await session.commit()
    return ChatOut(**result)
