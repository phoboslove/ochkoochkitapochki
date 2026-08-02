"""Reports endpoints — currently demo-only payloads, but the company filter
is enforced here so future per-tenant reports inherit the boundary."""
from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, get_current_user
from app.services.reports.service import ReportService

router = APIRouter()
service = ReportService()


@router.get("/monthly")
async def monthly(_user: CurrentUser = Depends(get_current_user)) -> dict:
    return service.monthly_demo()


@router.get("/dashboard")
async def dashboard(_user: CurrentUser = Depends(get_current_user)) -> dict:
    return service.dashboard_demo()
