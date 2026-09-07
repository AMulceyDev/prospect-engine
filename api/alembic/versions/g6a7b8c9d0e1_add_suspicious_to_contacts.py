"""add suspicious flag to contacts

Revision ID: g6a7b8c9d0e1
Revises: f5a6b7c8d9e0
Create Date: 2026-06-17 00:03:00.000000

NULL  = not yet evaluated
True  = suspect (OSM domain does not match the ownership-confirmed website)
False = reliable
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("suspicious", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("contacts", "suspicious")
