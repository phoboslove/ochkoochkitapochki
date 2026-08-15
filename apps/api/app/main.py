from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, log
from app.core.middleware import RequestIDMiddleware
from app.core.monitoring import init_monitoring
from app.core.preflight import env_checks, run_at_startup
from app.db.seed import init_and_seed

configure_logging()
init_monitoring()

app = FastAPI(
    title="Buchuchet API",
    version="0.1.0",
    description="AI Backoffice OS — orchestration layer",
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-request-id"],
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def _startup() -> None:
    run_at_startup()
    # Prod entrypoint runs `alembic upgrade head` first; init_and_seed is a
    # safe no-op once the demo tenant exists. For dev (SQLite) it creates
    # the schema directly and seeds the demo company.
    await init_and_seed()


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    from app.services.limits.usage import QuotaExceeded
    from app.services.billing.exceptions import (
        DocumentLimitExceededError, SubscriptionSuspendedError,
    )
    from app.api.v1.endpoints.auth import EmailNotVerifiedError
    rid = getattr(request.state, "request_id", "-")
    if isinstance(exc, EmailNotVerifiedError):
        return JSONResponse(
            status_code=403,
            content={"error": "email_not_verified", "email": exc.email,
                     "message": "Подтвердите почту, чтобы войти. Мы отправили код на ваш email.",
                     "support_id": rid},
        )
    if isinstance(exc, QuotaExceeded):
        return JSONResponse(
            status_code=402,
            content={"error": "quota_exceeded", "feature": exc.feature, "used": exc.used,
                     "limit": exc.limit, "support_id": rid},
        )
    if isinstance(exc, SubscriptionSuspendedError):
        return JSONResponse(
            status_code=402,
            content={"error": "subscription_suspended", "message": str(exc),
                     "period_end": exc.period_end.isoformat(), "support_id": rid},
        )
    if isinstance(exc, DocumentLimitExceededError):
        return JSONResponse(
            status_code=402,
            content={"error": "document_limit_exceeded", "message": str(exc),
                     "used": exc.used, "limit": exc.limit, "support_id": rid},
        )
    log.error("unhandled_exception", request_id=rid, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error",
                 "message": "Something went wrong on our side. Reference this support ID when reporting.",
                 "support_id": rid},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    """Deep readiness — DB and storage reachable; 503 otherwise."""
    from sqlalchemy import text
    from app.core.db import engine, engine_summary
    out: dict = {"db": "ok", "storage": "ok", "engine": engine_summary()}
    try:
        async with engine.begin() as conn:
            row = await conn.execute(text("SELECT version()" if out["engine"]["is_postgres"] else "SELECT 1"))
            v = row.scalar() if out["engine"]["is_postgres"] else None
            if v: out["postgres_version"] = str(v).split(" on ")[0]
    except Exception as exc:  # noqa: BLE001
        out["db"] = f"error: {exc}"
    try:
        from app.services.storage import get_storage
        from app.services.storage.local import LocalStorage
        s = get_storage()
        if isinstance(s, LocalStorage):
            s.put("__healthcheck__", b".", content_type="text/plain")
    except Exception as exc:  # noqa: BLE001
        out["storage"] = f"error: {exc}"
    status = 200 if all(v == "ok" for v in out.values()) else 503
    return JSONResponse(content=out, status_code=status)


@app.get("/health/diagnostics")
async def diagnostics() -> dict:
    """Configuration self-check (admin-gated in production)."""
    return {"checks": env_checks()}
