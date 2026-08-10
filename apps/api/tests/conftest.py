"""In-memory SQLite fixtures — isolated per test, never touches the real
DATABASE_URL (local file or prod Neon). Mirrors the "SQLite-friendly;
Postgres-ready" philosophy already stated in app/db/models.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.db import models  # noqa: F401  ensure models register on Base.metadata
from app.db.models import Company, Plan, Subscription, User
from app.core.security import hash_password


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def seeded(session: AsyncSession):
    """A company + owner user + a 2-doc/month plan + active subscription —
    the minimal fixture every enforcement test builds on."""
    now = datetime.utcnow()
    plan = Plan(
        id="plan_test", code="test", name="Test Plan", price_amount=Decimal(0),
        price_currency="KZT", billing_period="month",
        limit_documents_per_month=2, limit_users=5, limit_templates=5,
        allowed_integrations=None, is_active=True, sort_order=0,
        created_at=now, updated_at=now,
    )
    company = Company(id="c_test", name="Test Co", bin=None, settings={}, plan="free")
    user = User(
        id="u_test", company_id="c_test", email="test@example.com", name="Test Owner",
        role="OWNER", password_hash=hash_password("testpass123"), active=True,
        is_platform_admin=False,
    )
    subscription = Subscription(
        id="sub_test", company_id="c_test", plan_id="plan_test", status="active",
        period_start=now, period_end=now + timedelta(days=30),
        renewal_method="manual", grace_period_days=5,
    )
    session.add_all([plan, company, user, subscription])
    await session.commit()
    return {"company_id": "c_test", "user_id": "u_test", "plan_id": "plan_test", "subscription_id": "sub_test"}


@pytest_asyncio.fixture
async def platform_admin(session: AsyncSession):
    company = Company(id="c_platform_test", name="Platform Test", bin=None, settings={}, plan="enterprise")
    user = User(
        id="u_admin_test", company_id="c_platform_test", email="admin@example.com",
        name="Test Admin", role="OWNER", password_hash=hash_password("adminpass123"),
        active=True, is_platform_admin=True,
    )
    session.add_all([company, user])
    await session.commit()
    return {"company_id": "c_platform_test", "user_id": "u_admin_test"}
