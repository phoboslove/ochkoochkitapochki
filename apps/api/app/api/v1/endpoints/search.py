from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import CurrentUser, get_current_user
from app.services.search.service import SearchService

router = APIRouter()
service = SearchService()


@router.get("")
async def search(
    q: str = Query(..., min_length=1),
    type: str = Query("all"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    keyword = await service.keyword(session, company_id=user.company_id, q=q, type=type)  # type: ignore[arg-type]
    semantic = await service.semantic(session, company_id=user.company_id, q=q)
    return {"keyword": keyword, "semantic": semantic}
