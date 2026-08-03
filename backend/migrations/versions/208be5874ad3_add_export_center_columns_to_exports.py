"""add export center columns to exports

Purely additive. The `exports` table, its name, all of its pre-existing columns
and the `exportformat` / `exportstatus` enum types are untouched — this only
appends four columns needed by the Export Center:

  * `resource`       what the file contains (leads / search results / reports)
  * `filters`        the request that produced it, for history display and for
                     re-running the same selection in a background job
  * `error_message`  populated only when status is FAILED
  * `download_count` download audit trail

Every column carries a default, so rows written before this migration remain
valid without a backfill: `resource` defaults to LEADS, which is what those rows
in fact were.

Two things autogenerate got wrong and are corrected here:
  1. `op.add_column` with a `sa.Enum` does NOT emit `CREATE TYPE` on PostgreSQL
     (unlike `create_table`), so the new `exportresource` type is created
     explicitly first and dropped on downgrade.
  2. The generated `server_default` was the enum *value* ('leads'); the type's
     labels are the member *names* ('LEADS'), matching the existing
     `exportformat` type, so the lowercase default would have been rejected.

Revision ID: 208be5874ad3
Revises: 061f53392c57
Create Date: 2026-07-30 20:26:10.590734

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '208be5874ad3'
down_revision: Union[str, None] = '061f53392c57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Declared once and reused so upgrade/downgrade can't drift. `create_type=False`
# keeps add_column from trying to emit CREATE TYPE a second time.
export_resource_enum = postgresql.ENUM(
    'LEADS',
    'SEARCH_RESULTS',
    'DASHBOARD_REPORT',
    'ANALYTICS_REPORT',
    name='exportresource',
    create_type=False,
)


def upgrade() -> None:
    export_resource_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        'exports',
        sa.Column('resource', export_resource_enum, server_default='LEADS', nullable=False),
    )
    op.add_column('exports', sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('exports', sa.Column('error_message', sa.String(length=500), nullable=True))
    op.add_column('exports', sa.Column('download_count', sa.Integer(), server_default='0', nullable=False))
    op.create_index(op.f('ix_exports_resource'), 'exports', ['resource'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_exports_resource'), table_name='exports')
    op.drop_column('exports', 'download_count')
    op.drop_column('exports', 'error_message')
    op.drop_column('exports', 'filters')
    op.drop_column('exports', 'resource')
    # The type is only used by the column dropped above, so it goes too —
    # otherwise a re-run of upgrade() would find a stale type.
    export_resource_enum.drop(op.get_bind(), checkfirst=True)
