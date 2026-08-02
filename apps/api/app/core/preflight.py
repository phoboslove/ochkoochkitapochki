"""Startup diagnostics — non-fatal checks that surface misconfiguration early.

Each check returns ``(level, message)`` where level ∈ {"ok","warn","error"}.
Logged at startup; available via ``GET /health/diagnostics`` for ops dashboards.
"""
from __future__ import annotations

import os
from typing import Any

from app.core.config import settings
from app.core.logging import log


CheckResult = tuple[str, str]


def _ok(msg: str) -> CheckResult:    return ("ok", msg)
def _warn(msg: str) -> CheckResult:  return ("warn", msg)
def _err(msg: str) -> CheckResult:   return ("error", msg)


def env_checks() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    is_production = settings.app_env.lower() in ("production", "prod")

    def add(name: str, level: str, message: str) -> None:
        out.append({"check": name, "level": level, "message": message})

    # Required secrets
    if settings.jwt_secret in ("change-me", "", None):
        add("jwt_secret", "error", "JWT_SECRET is unset or default — rotate before exposing publicly.")
    else:
        add("jwt_secret", "ok", "JWT secret configured.")

    # Demo seed gating
    if settings.enable_demo_seed and is_production:
        add("demo_seed", "error",
            "APP_ENV=production but enable_demo_seed=True — refusing to "
            "spawn the demo@buchuchet.io account on a public deploy.")
    elif settings.enable_demo_seed:
        add("demo_seed", "warn",
            "Demo seed is ON. Set APP_ENV=production OR enable_demo_seed=False "
            "before deploying to a public server.")
    else:
        add("demo_seed", "ok", "Demo seed disabled.")

    # Database — report the *active* engine, not just the raw env var.
    from app.core.db import engine_summary
    s = engine_summary()
    label = f"{s['dialect']}+{s['driver']} → {s['host']}/{s['database']}"
    if s["is_neon"]:
        add("database", "ok", f"Neon Postgres active ({label}); ssl={s['ssl']}.")
    elif s["is_postgres"]:
        add("database", "ok", f"PostgreSQL active ({label}).")
    else:
        add("database", "error", f"SQLite is active ({label}) — set DATABASE_URL to your Neon DSN.")
    if s["is_postgres"] and not s["ssl"] and s["host"] not in (None, "localhost", "127.0.0.1"):
        add("database_ssl", "warn", "Postgres connected to a remote host without TLS — append ?sslmode=require.")

    # Storage
    if settings.storage_backend == "s3":
        if not (settings.s3_bucket and settings.s3_access_key and settings.s3_secret_key):
            add("storage", "error", "S3 backend selected but bucket/credentials are missing.")
        else:
            add("storage", "ok", f"S3 endpoint {settings.s3_endpoint} bucket={settings.s3_bucket}.")
    else:
        add("storage", "warn", "Local filesystem storage — files won't survive container rebuilds.")

    # AI
    if settings.openai_api_key or settings.anthropic_api_key:
        add("ai", "ok", "AI provider configured.")
    else:
        add("ai", "warn", "No AI keys set — orchestrator runs in regex-fallback mode.")

    # Email
    provider = os.environ.get("EMAIL_PROVIDER", "console").lower()
    if provider == "resend" and not os.environ.get("RESEND_API_KEY"):
        add("email", "error", "EMAIL_PROVIDER=resend but RESEND_API_KEY is unset.")
    elif provider == "postmark" and not os.environ.get("POSTMARK_TOKEN"):
        add("email", "error", "EMAIL_PROVIDER=postmark but POSTMARK_TOKEN is unset.")
    elif provider == "console":
        add("email", "warn", "Email provider=console — emails will be logged, not delivered.")
    else:
        add("email", "ok", f"Email provider={provider}.")

    # PDF engine
    try:
        from app.services.documents.pdf_engine import engine_status
        eng = engine_status()
        if eng.available:
            add("pdf_engine", "ok", f"PDF engine: {eng.name}")
        else:
            add("pdf_engine", "warn", eng.error or "PDF engine unavailable")
    except Exception as exc:  # noqa: BLE001
        add("pdf_engine", "warn", f"PDF probe error: {exc}")

    # Sentry
    if os.environ.get("SENTRY_DSN"):
        add("sentry", "ok", "Sentry DSN configured.")
    else:
        add("sentry", "warn", "Sentry not configured — errors won't be reported externally.")

    return out


def run_at_startup() -> None:
    for c in env_checks():
        getattr(log, c["level"] if c["level"] != "ok" else "info")(
            "preflight", check=c["check"], message=c["message"],
        )
