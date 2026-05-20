from fastapi import APIRouter

from app.services.reports.service import ReportService

router = APIRouter()
service = ReportService()


@router.get("/monthly")
async def monthly() -> dict:
    return service.monthly_demo()


@router.get("/dashboard")
async def dashboard() -> dict:
    return service.dashboard_demo()
