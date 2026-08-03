"""API providers, lead searches, per-provider search runs, website scans,
and exports."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import (
    ExportFormat,
    ExportResource,
    ExportStatus,
    ProviderCategory,
    ProviderStatus,
    SearchStatus,
)


class ApiProvider(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "api_providers"

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    category: Mapped[ProviderCategory] = mapped_column(nullable=False, index=True)
    status: Mapped[ProviderStatus] = mapped_column(default=ProviderStatus.HEALTHY, nullable=False)
    logo: Mapped[str | None] = mapped_column(String(16))
    description: Mapped[str | None] = mapped_column(Text)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usage_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Encrypted at rest via utils/crypto.py — never store plaintext here.
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    # Second credential, for providers that authenticate with a pair rather than
    # a single key — Mappls exchanges a client id *and* secret for an OAuth
    # token. Kept as its own column rather than packing JSON into the field
    # above, so each value stays independently readable and rotatable.
    api_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    # Credits charged per result sourced from this provider. Lets an expensive
    # provider cost more than a cheap one without a redeploy. Falls back to
    # settings.DEFAULT_SEARCH_CREDIT_COST_PER_RESULT when NULL.
    credit_cost: Mapped[int | None] = mapped_column(Integer, server_default="1")


class Search(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "searches"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    filters: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[SearchStatus] = mapped_column(default=SearchStatus.RUNNING, nullable=False, index=True)
    results_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    provider_runs: Mapped[list["SearchProviderRun"]] = relationship(
        back_populates="search", cascade="all, delete-orphan"
    )


class SearchProviderRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "search_provider_runs"

    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_providers.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SearchStatus] = mapped_column(default=SearchStatus.RUNNING, nullable=False)
    results_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    search: Mapped["Search"] = relationship(back_populates="provider_runs")


class WebsiteScan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "website_scans"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL")
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255))
    contact_person: Mapped[str | None] = mapped_column(String(255))
    confidence_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    emails: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))
    phones: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    gst_number: Mapped[str | None] = mapped_column(String(32))
    gst_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    social_links: Mapped[dict | None] = mapped_column(JSONB)
    ssl_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mobile_friendly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    load_time_ms: Mapped[int | None] = mapped_column(Integer)
    seo_score: Mapped[int | None] = mapped_column(SmallInteger)
    scan_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class Export(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "exports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[ExportFormat] = mapped_column(nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[ExportStatus] = mapped_column(default=ExportStatus.PROCESSING, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Export Center additions (additive; every existing column above is
    # untouched, and all four carry defaults so pre-existing rows stay valid) ---

    # What the file contains. Defaults to LEADS because that is what every row
    # written before this column existed was.
    # NOTE: the server default is the enum *member name* ("LEADS"), not its
    # value ("leads"). This codebase maps Python enums with SQLAlchemy's default
    # behaviour, so the Postgres type's labels are the member names — the
    # existing `exportformat` type is likewise CSV/EXCEL/PDF/JSON, not
    # csv/excel/pdf/json. A lowercase default here is rejected by the type.
    resource: Mapped[ExportResource] = mapped_column(
        default=ExportResource.LEADS, server_default=ExportResource.LEADS.name, nullable=False, index=True
    )
    # The request that produced this export (scope, filters, chosen columns).
    # Kept so history can show *what* was exported, and so a background job can
    # re-run the same selection after the request has ended.
    filters: Mapped[dict | None] = mapped_column(JSONB)
    # Populated only when status is FAILED — a failure with no reason is a
    # support ticket rather than a diagnosis.
    error_message: Mapped[str | None] = mapped_column(String(500))
    # Download audit trail: exports can carry the whole lead database, so how
    # often a file was fetched is worth recording.
    download_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
