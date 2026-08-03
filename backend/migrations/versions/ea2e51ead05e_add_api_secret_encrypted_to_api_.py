"""add api_secret_encrypted to api_providers

Purely additive. Providers that authenticate with a credential *pair* (Mappls
exchanges a client id and secret for an OAuth token) had nowhere to store the
second value, so per-workspace credentials could not be configured for them at
all. Nullable, so every existing row is valid without a backfill.

Revision ID: ea2e51ead05e
Revises: 3a6fd6f68951
Create Date: 2026-08-03 08:18:19.684681

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ea2e51ead05e'
down_revision: Union[str, None] = '3a6fd6f68951'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("api_providers", sa.Column("api_secret_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_providers", "api_secret_encrypted")
