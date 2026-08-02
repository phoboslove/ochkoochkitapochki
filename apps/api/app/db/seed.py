"""Initial seed: demo company, owner user, default invoice template."""
from __future__ import annotations

from sqlalchemy import select

from app.core.db import SessionLocal, engine, Base
from app.core.security import hash_password
from app.db import models  # noqa: F401
from sqlalchemy import text


_ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    # (table, column, type)
    ("templates", "status",             "VARCHAR DEFAULT 'UPLOADED'"),
    ("templates", "original_filename",  "VARCHAR"),
    ("templates", "file_hash",          "VARCHAR"),
    ("templates", "language",           "VARCHAR"),
    ("templates", "version",            "INTEGER DEFAULT 1"),
    ("templates", "parent_template_id", "VARCHAR"),
    ("templates", "detected_fields",    "JSON"),
    ("templates", "detected_tables",    "JSON"),
    ("templates", "mappings",           "JSON"),
    ("templates", "confidence",         "DOUBLE PRECISION"),
    ("templates", "last_render_at",     "TIMESTAMP"),
    ("templates", "last_error",         "TEXT"),
    ("templates", "updated_at",         "TIMESTAMP"),
    ("templates", "validation_score",   "INTEGER"),
    ("templates", "validation_warnings","JSON"),
    ("templates", "industry",           "VARCHAR"),
    ("templates", "converted_from_id",  "VARCHAR"),
]


async def _additive_migrations(conn) -> None:
    """Postgres-friendly idempotent column additions. Safe to run on every boot."""
    for table, col, coltype in _ADDITIVE_COLUMNS:
        try:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coltype}"))
        except Exception:  # noqa: BLE001
            # SQLite lacks IF NOT EXISTS for ADD COLUMN — best-effort fallback.
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
            except Exception:
                pass


DEMO_COMPANY_ID = "c_demo"
DEMO_USER_EMAIL = "demo@buchuchet.io"
DEMO_USER_PASSWORD = "demo1234"


_DEFAULT_INVOICE_TEMPLATE = """\
<!doctype html><html><body><h1>Invoice {{ invoice.number }}</h1></body></html>
"""

_DEFAULT_SETTINGS = {
    "branding": {"primary_color": "#0f172a", "logo_key": None},
    "invoice": {
        "currency_default": "KZT",
        "tax_default": 0,
        "due_in_days_default": 14,
        "numbering_format": "INV-{year}-{seq:04d}",
        "footer_note": "Thank you for your business.",
    },
    "ai": {
        "approval_required_for": ["send_invoice", "release_payment"],
        "model": "gpt-3.5-turbo",
    },
}


async def init_and_seed() -> None:
    # create_all is idempotent for *missing* tables. For existing tables we run
    # a tiny set of additive ALTERs guarded by IF NOT EXISTS — safe on Postgres,
    # safe on SQLite (silently ignored where the column already exists). Real
    # production deploys run Alembic from the container entrypoint instead.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _additive_migrations(conn)

    # Demo seed is dev-only. On production (APP_ENV=production) we never
    # create the credentialed demo@buchuchet.io account — its password is
    # in the repo, so creating it on a public server is a known breach.
    from app.core.config import settings
    if not settings.enable_demo_seed:
        from app.core.logging import log
        log.info("demo_seed_skipped", reason="enable_demo_seed=False",
                 app_env=settings.app_env)
        return

    async with SessionLocal() as s:
        if await s.scalar(select(models.Company).where(models.Company.id == DEMO_COMPANY_ID)):
            return
        s.add(models.Company(
            id=DEMO_COMPANY_ID, name="TOO Demo", bin="123456789012",
            tax_mode="simplified", settings=_DEFAULT_SETTINGS,
        ))
        await s.flush()  # Postgres validates FKs eagerly; Company must exist before its children.
        s.add(models.User(
            id="u_demo", company_id=DEMO_COMPANY_ID, email=DEMO_USER_EMAIL,
            name="Demo Owner", role="OWNER",
            password_hash=hash_password(DEMO_USER_PASSWORD),
        ))
        s.add_all([
            models.Client(id="cl_1", company_id=DEMO_COMPANY_ID, name="TOO ABC",
                          bin="123456789012", phone="+7 701 000 0001"),
            models.Client(id="cl_2", company_id=DEMO_COMPANY_ID, name="ИП Иванов",
                          bin="987654321098", phone="+7 705 000 0002"),
            models.Client(id="cl_3", company_id=DEMO_COMPANY_ID, name="TOO Beta",
                          bin="555555555555", phone="+7 707 000 0003"),
        ])
        s.add(models.Template(
            id="tpl_invoice_default", company_id=DEMO_COMPANY_ID,
            name="Default invoice", kind="invoice", format="html",
            body=_DEFAULT_INVOICE_TEMPLATE, is_default=True,
        ))
        await s.commit()
