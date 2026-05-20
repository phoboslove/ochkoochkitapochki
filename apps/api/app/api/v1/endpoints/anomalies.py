from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.services.anomalies.service import AnomalyService

router = APIRouter()
service = AnomalyService()


@router.get("")
async def list_anomalies(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await service.scan(session, user.company_id)
