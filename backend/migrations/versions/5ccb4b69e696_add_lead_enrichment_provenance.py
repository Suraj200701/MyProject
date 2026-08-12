"""add lead enrichment provenance

Adds where-did-this-come-from and how-far-did-we-get columns for contact
enrichment. Deliberately adds **no value columns**: the values enrichment
produces already have homes (`leads.phone`, `leads.email`, `companies.website`,
`companies.gst_number`), and a second copy would drift from the first.

`field_sources` and `social_profiles` are JSONB rather than one column per
field. The set of enriched fields is open-ended — alternate phone, WhatsApp,
contact person — and a schema migration per field is the wrong shape for that.
`field_sources` maps a field name to the page URL its value was read from.

All columns are nullable with no server default, so existing rows are untouched
and read as "never enriched". `enrichment_status` is indexed because the bulk UI
filters on it ("show me everything not yet enriched"); the JSONB columns are
displayed, not queried, so they are not.

Revision ID: 5ccb4b69e696
Revises: d9fe1453a42a
Create Date: 2026-08-05 09:41:12.338914

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5ccb4b69e696'
down_revision: Union[str, None] = 'd9fe1453a42a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("enrichment_status", sa.String(length=16), nullable=True))
    op.add_column("leads", sa.Column("enrichment_error", sa.String(length=500), nullable=True))
    op.add_column("leads", sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("leads", sa.Column("website_confidence", sa.SmallInteger(), nullable=True))
    op.add_column("leads", sa.Column("website_source", sa.String(length=500), nullable=True))
    op.add_column("leads", sa.Column("field_sources", postgresql.JSONB(), nullable=True))
    op.add_column("leads", sa.Column("social_profiles", postgresql.JSONB(), nullable=True))
    op.create_index("ix_leads_enrichment_status", "leads", ["enrichment_status"])


def downgrade() -> None:
    op.drop_index("ix_leads_enrichment_status", table_name="leads")
    for column in (
        "social_profiles",
        "field_sources",
        "website_source",
        "website_confidence",
        "enriched_at",
        "enrichment_error",
        "enrichment_status",
    ):
        op.drop_column("leads", column)
