"""Optional Sentry init — quietly no-op when no DSN or SDK isn't installed."""
from __future__ import annotations

import os

from app.core.logging import log


def init_monitoring() -> None:
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        log.info("sentry_sdk not installed — install `sentry-sdk[fastapi]` to enable")
        return
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES", "0.1")),
        environment=os.environ.get("APP_ENV", "dev"),
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        send_default_pii=False,
    )
    log.info("sentry_initialized")


def capture_workflow_failure(*, run_id: str, step: str, error: str, extra: dict | None = None) -> None:
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("workflow.run_id", run_id)
            scope.set_tag("workflow.step", step)
            for k, v in (extra or {}).items():
                scope.set_extra(k, v)
            sentry_sdk.capture_message(f"workflow_failed: {step}: {error}", level="error")
    except Exception:  # noqa: BLE001
        pass
    log.warning("workflow_failed", run_id=run_id, step=step, error=error, **(extra or {}))
