"""add analyses table

Revision ID: a1b2c3d4e5f6
Revises: fd2fb8d44688
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "fd2fb8d44688"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("website_id", sa.Integer(), sa.ForeignKey("websites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ownership_confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ownership_signals", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("emails", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("phones", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("tech_stack", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("wayback_first_seen", sa.String(), nullable=True),
        sa.Column("llm_score", sa.Integer(), nullable=True),
        sa.Column("llm_verdict", sa.String(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analyses_company_id", "analyses", ["company_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_analyses_company_id", "analyses")
    op.drop_table("analyses")
