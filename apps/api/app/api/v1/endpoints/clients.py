from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.db.models import Client

router = APIRouter()


@router.get("")
async def list_clients(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rows = await session.scalars(
        select(Client).where(Client.company_id == user.company_id).order_by(desc(Client.created_at)),
    )
    return [{"id": c.id, "name": c.name, "bin": c.bin, "phone": c.phone, "email": c.email} for c in rows]
