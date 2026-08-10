"""Platform-admin API — every route in this package is behind
require_platform_admin (404 for non-admins, see app/core/deps.py)."""
from fastapi import APIRouter

from app.api.v1.endpoints.admin import companies, dashboard, payments, plans

router = APIRouter()
router.include_router(dashboard.router)
router.include_router(companies.router)
router.include_router(payments.router)
router.include_router(plans.router)
