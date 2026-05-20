"""initial baseline — generated from current metadata.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-09
"""
from alembic import op

from app.core.db import Base
from app.db import models  # noqa: F401


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the entire initial schema from SQLAlchemy metadata.

    For new pilots this seeds an empty database in one shot. Subsequent
    migrations should be generated with ``alembic revision --autogenerate``.
    """
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
