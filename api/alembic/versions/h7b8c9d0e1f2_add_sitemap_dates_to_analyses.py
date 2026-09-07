"""add sitemap dates to analyses

Revision ID: h7b8c9d0e1f2
Revises: g6a7b8c9d0e1
Create Date: 2026-06-17

Adds two nullable columns to the analyses table (Lot C):
  - sitemap_last_modified : most recent <lastmod> date found in /sitemap.xml (YYYY-MM-DD)
  - sitemap_page_count    : number of <url> entries in the sitemap

Both are weak signals — lastmod is frequently auto-generated and page_count
depends on sitemap completeness. Store as-is for downstream scoring.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "g6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("sitemap_last_modified", sa.String(), nullable=True))
    op.add_column("analyses", sa.Column("sitemap_page_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "sitemap_page_count")
    op.drop_column("analyses", "sitemap_last_modified")
