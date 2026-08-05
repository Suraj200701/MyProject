"""Companies, leads, lead notes, and lead activity timeline."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import LeadStatus


class Company(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(150), index=True)
    company_type: Mapped[str | None] = mapped_column(String(100))
    revenue_band: Mapped[str | None] = mapped_column(String(50))
    website: Mapped[str | None] = mapped_column(String(255))
    gst_number: Mapped[str | None] = mapped_column(String(32))
    # Full street address as the source reported it. Local-business sources
    # (Google Maps exports, Mappls POIs) lead with a formatted address and often
    # nothing else location-wise, so dropping it loses the most useful field
    # they provide. `city` stays separate because it is what dedup and filtering
    # match on.
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(150), index=True)
    country: Mapped[str | None] = mapped_column(String(150), index=True)
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6))
    rating: Mapped[float | None] = mapped_column(Numeric(2, 1))

    leads: Mapped[list["Lead"]] = relationship(back_populates="company")


class Lead(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "leads"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))

    lead_score: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False, index=True)
    status: Mapped[LeadStatus] = mapped_column(default=LeadStatus.NEW, nullable=False, index=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))
    ai_summary: Mapped[str | None] = mapped_column(Text)

    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("api_providers.id", ondelete="SET NULL")
    )
    # Where this lead came from, in a form that survives the provider row being
    # deleted (`provider_id` is SET NULL) and that can also describe origins with
    # no catalogue row at all — the website scanner, a CSV import, manual entry.
    #
    # Plain strings rather than a Postgres enum: every new origin would otherwise
    # need an ALTER TYPE migration, and these are descriptive labels, not a state
    # machine. Both are nullable, so existing rows stay valid and untouched.
    source_type: Mapped[str | None] = mapped_column(String(16), index=True)
    source_provider: Mapped[str | None] = mapped_column(String(64))
    search_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("searches.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    company: Mapped["Company"] = relationship(back_populates="leads")
    notes: Mapped[list["LeadNote"]] = relationship(back_populates="lead", cascade="all, delete-orphan")
    activities: Mapped[list["LeadActivity"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="LeadActivity.created_at"
    )


class LeadNote(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "lead_notes"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="notes")


class LeadActivity(Base, UUIDPrimaryKeyMixin):
    """Timeline entries: 'Discovered via Google Places', 'AI score calculated', etc."""

    __tablename__ = "lead_activities"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="activities")
