"""SQLAlchemy async engine + session factory.

DSN normalization:
  * ``postgres://`` and ``postgresql://`` are auto-promoted to
    ``postgresql+asyncpg://`` so common Neon / Heroku / Railway URLs work.
  * Neon hosts get ``sslmode`` mapped to ``ssl=true`` (asyncpg uses ``ssl`` kwarg,
    not ``sslmode``).
"""
from collections.abc import AsyncIterator
from urllib.parse import urlparse, urlunparse

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import log


def _normalize_dsn(raw: str) -> tuple[str, dict]:
    """Return (sqlalchemy_url, connect_args). asyncpg doesn't accept sslmode=, so
    we strip it from the query and pass ``ssl=True`` via ``connect_args`` instead.
    """
    url = raw.strip()
    connect_args: dict = {}

    # Promote driverless DSNs to asyncpg.
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    if "asyncpg" in url:
        parts = urlparse(url)
        query = parts.query
        # Strip libpq-style flags that asyncpg doesn't understand.
        if "sslmode=" in query or "channel_binding=" in query:
            keep: list[str] = []
            wants_ssl = False
            for kv in query.split("&"):
                if kv.startswith("sslmode="):
                    if kv.split("=", 1)[1] in ("require", "verify-ca", "verify-full"):
                        wants_ssl = True
                    continue
                if kv.startswith("channel_binding="):
                    continue
                if kv:
                    keep.append(kv)
            url = urlunparse(parts._replace(query="&".join(keep)))
            if wants_ssl:
                connect_args["ssl"] = True
        # Neon always wants TLS.
        if "neon.tech" in (parts.hostname or "") and "ssl" not in connect_args:
            connect_args["ssl"] = True

    return url, connect_args


_DSN, _CONNECT_ARGS = _normalize_dsn(settings.database_url)

# Pool sizing tuned for serverless Postgres (Neon). 5 long-lived + 5 overflow
# keeps us well under typical 100-conn limits.
_engine_kwargs: dict = {"pool_pre_ping": True, "connect_args": _CONNECT_ARGS}
if "sqlite" not in _DSN:
    _engine_kwargs.update({"pool_size": 5, "max_overflow": 5,
                           "pool_recycle": 1800, "pool_timeout": 30})

engine = create_async_engine(_DSN, **_engine_kwargs)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def engine_summary() -> dict:
    """Public snapshot used by /health and startup logs."""
    sync_url = engine.sync_engine.url
    return {
        "dialect": sync_url.get_dialect().name,
        "driver":  sync_url.get_dialect().driver,
        "host":    sync_url.host,
        "database": sync_url.database,
        "is_postgres": sync_url.get_dialect().name == "postgresql",
        "is_neon":    "neon.tech" in (sync_url.host or ""),
        "pool":       _engine_kwargs.get("pool_size"),
        "ssl":        bool(_CONNECT_ARGS.get("ssl")),
    }


@event.listens_for(engine.sync_engine, "first_connect")
def _on_first_connect(_dbapi_conn, _record):  # type: ignore[no-redef]
    s = engine_summary()
    log.info(
        "db.connected",
        dialect=s["dialect"], driver=s["driver"], host=s["host"],
        database=s["database"], is_neon=s["is_neon"], ssl=s["ssl"],
    )


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
