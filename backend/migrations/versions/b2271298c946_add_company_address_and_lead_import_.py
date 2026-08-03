"""add company address and lead import history

Additive only:
  * `companies.address` — local-business sources (Google Maps exports, Mappls
    POIs) lead with a formatted address; there was nowhere to put it, so it was
    being discarded.
  * `lead_imports` — one row per import run, so "what did that run do?" is
    answerable after the leads themselves have been edited.

Enum types are created explicitly with `checkfirst=True` and `create_type=False`
on the column: `op.create_table` does not reliably emit `CREATE TYPE` on its own,
and `server_default` must use the enum **member name** (uppercase), not its
value — that is what SQLAlchemy writes for these enums.

Revision ID: b2271298c946
Revises: ea2e51ead05e
Create Date: 2026-08-04 00:37:38.403722

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2271298c946'
down_revision: Union[str, None] = 'ea2e51ead05e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


import_source = postgresql.ENUM(
    "CSV_UPLOAD",
    "GOOGLE_MAPS_EXTRACTOR",
    name="importsource",
    create_type=False,
)
import_status = postgresql.ENUM(
    "PROCESSING",
    "COMPLETED",
    "COMPLETED_EMPTY",
    "FAILED",
    name="importstatus",
    create_type=False,
)


def upgrade() -> None:
    op.add_column("companies", sa.Column("address", sa.String(length=500), nullable=True))

    bind = op.get_bind()
    import_source.create(bind, checkfirst=True)
    import_status.create(bind, checkfirst=True)

    op.create_table(
        "lead_imports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("source", import_source, nullable=False),
        sa.Column("status", import_status, server_default="PROCESSING", nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("keyword", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicates_skipped", sa.Integer(), server_default="0", nullable=False),
        sa.Column("invalid_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("enriched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("row_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("dedup_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_imports_organization_id", "lead_imports", ["organization_id"])
    op.create_index("ix_lead_imports_user_id", "lead_imports", ["user_id"])
    op.create_index("ix_lead_imports_source", "lead_imports", ["source"])
    op.create_index("ix_lead_imports_status", "lead_imports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_lead_imports_status", table_name="lead_imports")
    op.drop_index("ix_lead_imports_source", table_name="lead_imports")
    op.drop_index("ix_lead_imports_user_id", table_name="lead_imports")
    op.drop_index("ix_lead_imports_organization_id", table_name="lead_imports")
    op.drop_table("lead_imports")

    bind = op.get_bind()
    import_status.drop(bind, checkfirst=True)
    import_source.drop(bind, checkfirst=True)

    op.drop_column("companies", "address")
