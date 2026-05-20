"""Alembic env — sync engine, autogenerate against SQLAlchemy metadata.

Reads ``ALEMBIC_URL`` (sync DSN, e.g. postgresql+psycopg://…) so we don't ship
asyncpg into the migration runner. ``DATABASE_URL`` is reused as a fallback
with a best-effort dialect rewrite.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.db import Base
from app.db import models  # noqa: F401  ensure models register


config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

url = os.environ.get("ALEMBIC_URL") or os.environ.get("DATABASE_URL", "")
url = url.replace("+asyncpg", "+psycopg").replace("+aiosqlite", "")
config.set_main_option("sqlalchemy.url", url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True, render_as_batch=url.startswith("sqlite"))
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
