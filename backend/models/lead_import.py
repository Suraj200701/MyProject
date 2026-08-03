"""Import run history.

One row per import attempt, successful or not. Kept because a lead import is
destructive-ish in aggregate — it can add hundreds of rows to a shared CRM — and
"what did that run actually do?" is the first question when the numbers look
wrong. The counts are denormalized onto the row rather than recomputed, since the
leads themselves get edited, merged and deleted afterwards.

Failed runs are recorded too: an import that blew up leaves evidence instead of
silence.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ImportSource, ImportStatus


class LeadImport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_imports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    source: Mapped[ImportSource] = mapped_column(nullable=False, index=True)
    status: Mapped[ImportStatus] = mapped_column(
        default=ImportStatus.PROCESSING, nullable=False, index=True
    )

    file_name: Mapped[str | None] = mapped_column(String(255))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)

    # The Google Maps query this file came from. Null for a plain CSV upload.
    # Stored so the history reads "Dentists in Ahmedabad — 84 leads" rather than
    # "export(3).csv", which is unidentifiable a week later.
    keyword: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))

    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enriched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Per-row rejections, capped when persisted — a pathological file must not
    # write megabytes of JSON into the history table.
    row_errors: Mapped[list | None] = mapped_column(JSONB)
    # Which dedup rule matched, for explaining a high duplicate count.
    dedup_signals: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization = relationship("Organization")
    user = relationship("User")
