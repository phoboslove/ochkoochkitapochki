"""subscriptions.manually_suspended — distinguish admin-initiated suspend
from the natural past_due->suspended transition, so the self-healing status
refresh doesn't silently revert an admin suspend while period_end is still
in the future.

Revision ID: 0004_manually_suspended_flag
Revises: 0003_seed_plans_and_backfill
Create Date: 2026-08-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_manually_suspended_flag"
down_revision = "0003_seed_plans_and_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("manually_suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "manually_suspended")
