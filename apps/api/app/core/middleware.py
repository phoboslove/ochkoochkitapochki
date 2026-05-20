"""Request-ID middleware + structured access logging."""
from __future__ import annotations

import uuid
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import log


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.error("request.error", request_id=rid, path=request.url.path,
                      method=request.method)
            raise
        duration_ms = int((perf_counter() - started) * 1000)
        response.headers["x-request-id"] = rid
        if request.url.path.startswith("/api"):
            log.info("request", request_id=rid, method=request.method,
                     path=request.url.path, status=response.status_code,
                     duration_ms=duration_ms)
        return response
