"""seed plans, backfill existing companies to trial, seed platform admin

Revision ID: 0003_seed_plans_and_backfill
Revises: 0002_billing_tables
Create Date: 2026-08-10
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

import sqlalchemy as sa
from alembic import op

revision = "0003_seed_plans_and_backfill"
down_revision = "0002_billing_tables"
branch_labels = None
depends_on = None

PLATFORM_ADMIN_EMAIL = "aetherisintelligencestudio@gmail.com"

# code, name, price_amount, docs/mo, users, templates, sort_order
PLAN_ROWS = [
    ("trial",      "Trial",      0,      20,   3,   5,   0),
    ("basic",      "Basic",      15000,  100,  5,   15,  1),
    ("pro",        "Pro",        45000,  500,  20,  50,  2),
    ("enterprise", "Enterprise", 150000, 5000, 100, 500, 3),
]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.utcnow()

    plans = sa.table(
        "plans",
        sa.column("id", sa.String), sa.column("code", sa.String), sa.column("name", sa.String),
        sa.column("price_amount", sa.Numeric), sa.column("price_currency", sa.String),
        sa.column("billing_period", sa.String),
        sa.column("limit_documents_per_month", sa.Integer), sa.column("limit_users", sa.Integer),
        sa.column("limit_templates", sa.Integer), sa.column("allowed_integrations", sa.JSON),
        sa.column("is_active", sa.Boolean), sa.column("sort_order", sa.Integer),
        sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    plan_ids: dict[str, str] = {}
    for code, name, price, docs, users, templates, order in PLAN_ROWS:
        pid = f"plan_{code}"
        plan_ids[code] = pid
        bind.execute(plans.insert().values(
            id=pid, code=code, name=name, price_amount=price, price_currency="KZT",
            billing_period="month", limit_documents_per_month=docs, limit_users=users,
            limit_templates=templates, allowed_integrations=None, is_active=True,
            sort_order=order, created_at=now, updated_at=now,
        ))

    # Backfill every existing company onto trial, 30 days from now — so
    # nothing breaks the moment this deploys.
    companies = sa.table(
        "companies",
        sa.column("id", sa.String), sa.column("name", sa.String), sa.column("bin", sa.String),
        sa.column("tax_mode", sa.String), sa.column("country_code", sa.String),
        sa.column("settings", sa.JSON), sa.column("logo_key", sa.String),
        sa.column("plan", sa.String), sa.column("onboarded", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )
    subscriptions = sa.table(
        "subscriptions",
        sa.column("id", sa.String), sa.column("company_id", sa.String), sa.column("plan_id", sa.String),
        sa.column("status", sa.String), sa.column("period_start", sa.DateTime),
        sa.column("period_end", sa.DateTime), sa.column("renewal_method", sa.String),
        sa.column("grace_period_days", sa.Integer),
        sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime),
    )
    company_ids = [row[0] for row in bind.execute(sa.select(companies.c.id)).fetchall()]
    for cid in company_ids:
        bind.execute(subscriptions.insert().values(
            id=f"sub_{uuid.uuid4().hex[:12]}", company_id=cid, plan_id=plan_ids["trial"],
            status="trialing", period_start=now, period_end=now + timedelta(days=30),
            renewal_method="manual", grace_period_days=5, created_at=now, updated_at=now,
        ))

    # Dedicated non-customer company for platform-admin accounts.
    bind.execute(companies.insert().values(
        id="c_platform", name="Wagwan Platform", bin=None, tax_mode=None, country_code="KZ",
        settings={}, logo_key=None, plan="enterprise", onboarded=True, created_at=now,
    ))

    from passlib.hash import bcrypt
    generated_password = secrets.token_urlsafe(18)
    password_hash = bcrypt.hash(generated_password)

    users = sa.table(
        "users",
        sa.column("id", sa.String), sa.column("company_id", sa.String), sa.column("email", sa.String),
        sa.column("name", sa.String), sa.column("role", sa.String), sa.column("password_hash", sa.String),
        sa.column("active", sa.Boolean), sa.column("is_platform_admin", sa.Boolean),
        sa.column("notify_telegram", sa.Boolean), sa.column("notify_email", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )
    bind.execute(users.insert().values(
        id=f"u_{uuid.uuid4().hex[:10]}", company_id="c_platform", email=PLATFORM_ADMIN_EMAIL,
        name="Platform Admin", role="OWNER", password_hash=password_hash, active=True,
        is_platform_admin=True, notify_telegram=False, notify_email=True, created_at=now,
    ))

    print("\n" + "=" * 72)
    print(f"PLATFORM ADMIN CREATED: {PLATFORM_ADMIN_EMAIL}")
    print(f"TEMPORARY PASSWORD:     {generated_password}")
    print("Relay this to the operator out-of-band; it is not stored in git or logs.")
    print("=" * 72 + "\n")


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM users WHERE company_id = 'c_platform'"))
    bind.execute(sa.text("DELETE FROM companies WHERE id = 'c_platform'"))
    bind.execute(sa.text("DELETE FROM subscriptions"))
    bind.execute(sa.text("DELETE FROM plans"))
