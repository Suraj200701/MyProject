"""Personal API keys, generic settings key-value store, and backup
snapshot records (Settings page: API Keys, Theme/Notifications/Backup
sections)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import SettingScope


class ApiKey(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Personal API keys a user generates to call the LeadMaster API
    programmatically — distinct from `api_providers`, which are the
    third-party data sources LeadMaster itself calls."""

    __tablename__ = "api_keys"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Setting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Flexible key-value settings store (theme choice, backup frequency,
    locale overrides, ...) scoped to a user, an organization, or global."""

    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("scope", "scope_id", "key", name="uq_setting_scope_key"),)

    scope: Mapped[SettingScope] = mapped_column(nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    key: Mapped[str] = mapped_column(String(150), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)


class BackupSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "backup_snapshots"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
