"""Lightweight in-memory rate limiter — no external dependency.

Trade-off for the beta: limits are per-process, so a multi-worker uvicorn
deploy effectively multiplies allowance by worker count. That's acceptable
because the goal is "stop scripted brute-force from a single IP", not
strict billing-grade rate control. Swap to Redis-backed counters for
paid-customer scale.

Usage:
    from fastapi import Depends, Request
    from app.core.ratelimit import rate_limit
    @router.post("/login", dependencies=[Depends(rate_limit("auth", 5, 60))])
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Callable

from fastapi import HTTPException, Request

from app.core.logging import log


class _SlidingWindow:
    """One sliding-window counter per (bucket, key).

    `bucket` separates protected endpoints from each other; `key` is the
    per-request identity (IP, user id). Counters are evicted lazily when
    the oldest timestamp falls outside the window.
    """
    def __init__(self) -> None:
        self._counters: dict[tuple[str, str], deque[float]] = {}
        self._lock = Lock()

    def hit(self, *, bucket: str, key: str, limit: int, window_s: float) -> bool:
        """Record a hit. Returns True if the request is allowed."""
        now = time.monotonic()
        with self._lock:
            dq = self._counters.setdefault((bucket, key), deque())
            cutoff = now - window_s
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            return True


_window = _SlidingWindow()


def _client_key(request: Request) -> str:
    """Best-effort caller identity. Honours common reverse-proxy headers
    when present (we sit behind nginx in prod) and falls back to socket peer.
    """
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return getattr(getattr(request, "client", None), "host", "") or "unknown"


def rate_limit(bucket: str, limit: int, window_s: float) -> Callable:
    """FastAPI dependency factory. Raises 429 when the caller exceeds the
    bucket's quota in the rolling window."""
    async def _dep(request: Request) -> None:
        key = _client_key(request)
        if not _window.hit(bucket=bucket, key=key, limit=limit, window_s=window_s):
            log.warning(
                "rate_limit_hit", bucket=bucket, key=key,
                limit=limit, window_s=window_s, path=request.url.path,
            )
            raise HTTPException(
                status_code=429,
                detail=f"rate limit exceeded for {bucket}: "
                       f"{limit} requests per {int(window_s)}s",
                headers={"Retry-After": str(int(window_s))},
            )
    return _dep
