"""add contacts table

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id",
            sa.Integer(),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(), nullable=False),    # "email" | "phone"
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),  # "osm" | "page" | "rne"
        sa.Column("nature", sa.String(), nullable=True),   # "nominatif" | "generique" | NULL
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])
    op.create_unique_constraint(
        "uq_contacts_company_type_value", "contacts", ["company_id", "type", "value"]
    )


def downgrade() -> None:
    op.drop_table("contacts")
