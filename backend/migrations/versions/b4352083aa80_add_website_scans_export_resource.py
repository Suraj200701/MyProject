"""add website_scans export resource

Adds one member to the existing `exportresource` enum so website scans can be
exported through the Export Center like any other resource.

Notes on the SQL:

* Postgres stores the enum **member names** SQLAlchemy generates (uppercase), so
  the value added is `WEBSITE_SCANS`, not `website_scans`.
* `ADD VALUE ... BEFORE` keeps the declaration order matching `models/enums.py`.
  Order is cosmetic for correctness but makes `\\dT+ exportresource` match the
  code, which is what someone debugging will compare.
* `IF NOT EXISTS` makes the upgrade re-runnable.

Downgrade removes the member. Postgres cannot `DROP VALUE` from an enum, so the
type is rebuilt — and any row still using the value would block that, which is
correct: silently rewriting those rows to a different resource would misreport
what those export files contain.

Revision ID: b4352083aa80
Revises: b2271298c946
Create Date: 2026-08-04 07:37:59.094449

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b4352083aa80'
down_revision: Union[str, None] = 'b2271298c946'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE exportresource ADD VALUE IF NOT EXISTS 'WEBSITE_SCANS' BEFORE 'DASHBOARD_REPORT'"
    )


def downgrade() -> None:
    # Rebuild the type without the member. Fails loudly if any export row still
    # references it, which is the right outcome — those rows describe real files.
    #
    # The column's server_default has to be dropped first and restored after:
    # Postgres refuses the type change otherwise with
    # `default for column "resource" cannot be cast automatically to type
    # exportresource`, because it will not re-cast the default expression itself.
    op.execute("ALTER TABLE exports ALTER COLUMN resource DROP DEFAULT")
    op.execute("ALTER TYPE exportresource RENAME TO exportresource_old")
    op.execute(
        "CREATE TYPE exportresource AS ENUM "
        "('LEADS', 'SEARCH_RESULTS', 'DASHBOARD_REPORT', 'ANALYTICS_REPORT')"
    )
    op.execute(
        "ALTER TABLE exports ALTER COLUMN resource TYPE exportresource "
        "USING resource::text::exportresource"
    )
    op.execute("DROP TYPE exportresource_old")
    # Restore the default the earlier migration set (member NAME, not value).
    op.execute("ALTER TABLE exports ALTER COLUMN resource SET DEFAULT 'LEADS'")
