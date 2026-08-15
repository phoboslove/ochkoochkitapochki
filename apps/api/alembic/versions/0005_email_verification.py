"""email verification — users.email_verified + email_verifications table.

Existing users are backfilled to email_verified=true (grandfathered — they
already have a working account, don't lock anyone out). New self-registered
users default to false and must confirm a 6-digit code before they can log
in; admin-created and invited users are marked verified at creation time
since those flows already prove the email another way.

Revision ID: 0005_email_verification
Revises: 0004_manually_suspended_flag
Create Date: 2026-08-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_email_verification"
down_revision = "0004_manually_suspended_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "email_verifications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sent_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_email_verifications_user_id", "email_verifications", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_email_verifications_user_id", table_name="email_verifications")
    op.drop_table("email_verifications")
    op.drop_column("users", "email_verified")
