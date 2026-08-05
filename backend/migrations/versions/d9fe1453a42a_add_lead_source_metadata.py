"""add lead source metadata

Records where each lead came from, so Map Mode and API Mode results are
distinguishable in the lead table and in exports.

Both columns are nullable with no server default. Existing rows keep NULL, which
reads correctly as "recorded before provenance was tracked" — backfilling them
would be inventing history, and `provider_id` is only a partial signal (it is
SET NULL when a provider row is deleted, and was never set for scanner, import
or manual leads).

Plain VARCHAR rather than Postgres enums: new origins would otherwise each need
an ALTER TYPE, and these are descriptive labels rather than a state machine. The
allowed values live in `models.enums.LeadSourceType`.

`source_type` is indexed because filtering the lead table by origin ("show me
what Map Mode found") is the reason it exists. `source_provider` is not — it is
displayed, not filtered on.

Revision ID: d9fe1453a42a
Revises: b4352083aa80
Create Date: 2026-08-05 00:11:04.882170

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd9fe1453a42a'
down_revision: Union[str, None] = 'b4352083aa80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("source_type", sa.String(length=16), nullable=True))
    op.add_column("leads", sa.Column("source_provider", sa.String(length=64), nullable=True))
    op.create_index("ix_leads_source_type", "leads", ["source_type"])


def downgrade() -> None:
    op.drop_index("ix_leads_source_type", table_name="leads")
    op.drop_column("leads", "source_provider")
    op.drop_column("leads", "source_type")
