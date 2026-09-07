"""Structure noms_de_domaine as list[{domain, source}]

Revision ID: d3e4f5a6b7c8
Revises: c3d4e5f6a7b8
Create Date: 2026-06-17 00:01:00.000000

Each entry in noms_de_domaine becomes {"domain": str, "source": "rne"|"osm"}.
Previously the column stored plain strings with no source attribution.

Migration strategy (defensive / idempotent):
  - JSON string element  → wrapped as {"domain": value, "source": "rne"}
  - JSON object element  → left unchanged (already migrated)

Known limitation: strings written by OSM before this migration are
indistinguishable from RNE strings and will be labeled "rne" by default.
In a development context, drop + re-ingest for clean data.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE companies
        SET noms_de_domaine = (
            SELECT COALESCE(
                jsonb_agg(
                    CASE
                        WHEN jsonb_typeof(elem) = 'string'
                        THEN jsonb_build_object('domain', elem #>> '{}', 'source', 'rne')
                        ELSE elem
                    END
                ),
                '[]'::jsonb
            )
            FROM jsonb_array_elements(noms_de_domaine) AS elem
        )
        WHERE noms_de_domaine != '[]'::jsonb
    """)


def downgrade() -> None:
    # Unwrap dict entries back to plain strings; source information is lost.
    op.execute("""
        UPDATE companies
        SET noms_de_domaine = (
            SELECT COALESCE(
                jsonb_agg(
                    CASE
                        WHEN jsonb_typeof(elem) = 'object'
                        THEN to_jsonb(elem ->> 'domain')
                        ELSE elem
                    END
                ),
                '[]'::jsonb
            )
            FROM jsonb_array_elements(noms_de_domaine) AS elem
        )
        WHERE noms_de_domaine != '[]'::jsonb
    """)
