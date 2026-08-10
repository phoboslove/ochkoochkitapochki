"""billing tables — plans, subscriptions, payments, usage_counters + platform admin flag

Revision ID: 0002_billing_tables
Revises: 0001_initial
Create Date: 2026-08-10
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_billing_tables"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "plans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("price_currency", sa.String(), nullable=False, server_default="KZT"),
        sa.Column("billing_period", sa.String(), nullable=False, server_default="month"),
        sa.Column("limit_documents_per_month", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("limit_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("limit_templates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allowed_integrations", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_plans_code", "plans", ["code"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="trialing"),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("renewal_method", sa.String(), nullable=False, server_default="manual"),
        sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_subscriptions_company_id", "subscriptions", ["company_id"], unique=True)
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    op.create_table(
        "payments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("subscription_id", sa.String(), sa.ForeignKey("subscriptions.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="KZT"),
        sa.Column("status", sa.String(), nullable=False, server_default="succeeded"),
        sa.Column("method", sa.String(), nullable=False, server_default="manual"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("provider_ref", sa.String(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_payments_company_id", "payments", ["company_id"])
    op.create_index("ix_payments_subscription_id", "payments", ["subscription_id"])

    op.create_table(
        "usage_counters",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("documents_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("company_id", "period", name="uq_usage_counters_company_period"),
    )
    op.create_index("ix_usage_counters_company_id", "usage_counters", ["company_id"])
    op.create_index("ix_usage_counters_period", "usage_counters", ["period"])


def downgrade() -> None:
    op.drop_table("usage_counters")
    op.drop_table("payments")
    op.drop_table("subscriptions")
    op.drop_index("ix_plans_code", table_name="plans")
    op.drop_table("plans")
    op.drop_column("users", "is_platform_admin")
