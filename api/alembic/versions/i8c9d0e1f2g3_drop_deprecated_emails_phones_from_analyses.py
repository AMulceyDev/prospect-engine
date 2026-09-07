"""drop deprecated emails and phones columns from analyses

Revision ID: i8c9d0e1f2g3
Revises: h7b8c9d0e1f2
Create Date: 2026-06-18

Removes the two DEPRECATED JSONB columns from the analyses table.
Canonical contacts are now written exclusively to the contacts table
(source="page") by _upsert_page_contacts() in services/analyze.py.
The frontend reads company.contacts[] — these columns are no longer
read by any schema, service, or view.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "i8c9d0e1f2g3"
down_revision: Union[str, Sequence[str], None] = "h7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("analyses", "emails")
    op.drop_column("analyses", "phones")


def downgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column(
            "phones",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "emails",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
