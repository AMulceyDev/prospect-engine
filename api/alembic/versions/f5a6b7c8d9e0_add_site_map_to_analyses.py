"""add site map fields to analyses

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-06-17 00:02:00.000000

Adds the lot-A "site map" columns to the analyses table:
  - internal_links / external_links : lists of URLs collected during shallow crawl
  - has_legal_page    : mentions légales / CGU / politique de confidentialité found
  - has_contact_info  : email or phone found on the site
  - provider_hint     : text/URL of the web agency found in the footer (nullable)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("internal_links", JSONB(), nullable=False, server_default="[]"))
    op.add_column("analyses", sa.Column("external_links", JSONB(), nullable=False, server_default="[]"))
    op.add_column("analyses", sa.Column("has_legal_page", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("analyses", sa.Column("has_contact_info", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("analyses", sa.Column("provider_hint", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "provider_hint")
    op.drop_column("analyses", "has_contact_info")
    op.drop_column("analyses", "has_legal_page")
    op.drop_column("analyses", "external_links")
    op.drop_column("analyses", "internal_links")
