"""add skipped to searchstatus enum

Why
---
A provider with no credentials was recorded as FAILED, because `searchstatus`
had no member for "did not run". Every search therefore reported half a dozen
failed integrations, which is both alarming and untrue.

Postgres enum labels are the Python member **names** (uppercase), not the
values — matching how `6db480726061_initial_schema` created this type.

Reversibility
-------------
Postgres cannot drop an enum label, so the downgrade recreates the type without
SKIPPED. Existing SKIPPED rows are mapped back to FAILED first, which is exactly
the pre-migration representation, so a down/up round trip is lossless in
meaning even though it cannot be lossless in detail.

Revision ID: 3a6fd6f68951
Revises: 208be5874ad3
Create Date: 2026-08-03 06:38:39.209005

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3a6fd6f68951'
down_revision: Union[str, None] = '208be5874ad3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [("searches", "status"), ("search_provider_runs", "status")]


def upgrade() -> None:
    # ADD VALUE is allowed inside a transaction from Postgres 12 onward as long
    # as the new label is not used in that same transaction — it isn't here.
    op.execute("ALTER TYPE searchstatus ADD VALUE IF NOT EXISTS 'SKIPPED'")


def downgrade() -> None:
    # No SKIPPED rows may survive, or the cast to the rebuilt type fails.
    for table, column in _COLUMNS:
        op.execute(f"UPDATE {table} SET {column} = 'FAILED' WHERE {column} = 'SKIPPED'")

    op.execute("ALTER TYPE searchstatus RENAME TO searchstatus_old")
    op.execute("CREATE TYPE searchstatus AS ENUM ('RUNNING', 'COMPLETED', 'FAILED')")
    for table, column in _COLUMNS:
        # The DEFAULT references the old type and blocks the ALTER, so drop it
        # and restore it against the new one.
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE searchstatus USING {column}::text::searchstatus"
        )
    op.execute("DROP TYPE searchstatus_old")
