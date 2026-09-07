"""add lighthouse fields to analyses

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("lighthouse_scores", JSONB(), nullable=True))
    op.add_column("analyses", sa.Column("lighthouse_seo", JSONB(), nullable=True))
    op.add_column("analyses", sa.Column("lighthouse_remarks", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "lighthouse_remarks")
    op.drop_column("analyses", "lighthouse_seo")
    op.drop_column("analyses", "lighthouse_scores")
