"""Pydantic schemas for leads, companies, notes, and the activity
timeline.

`LeadOut` intentionally mirrors the frontend's flattened `Lead` shape
(see src/lib/types.ts and src/lib/mock-data.ts) — the frontend denormalizes
company + lead into a single object, so this schema joins Lead+Company
(and resolves the provider name) into the same flat shape rather than
nesting a `company` object. This keeps a future frontend repoint to the
real API a near no-op.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from models.enums import LeadStatus


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    industry: str | None = None
    company_type: str | None = None
    revenue_band: str | None = None
    website: str | None = None
    gst_number: str | None = None
    city: str | None = None
    country: str | None = None
    lat: float | None = None
    lng: float | None = None
    rating: float | None = None

    model_config = {"from_attributes": True}


class LeadOut(BaseModel):
    """Flattened lead+company+provider view, matching the frontend mock
    `Lead` shape. Built via `from_lead()` since `provider` (the provider's
    *name*) isn't a plain ORM attribute on `Lead` — it requires resolving
    `Lead.provider_id` against the `api_providers` table, and `company`
    here is the company *name* string, not the nested `Company` object.
    """

    id: uuid.UUID
    company: str
    industry: str | None = None
    city: str | None = None
    country: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    revenue_band: str | None = None
    lead_score: int
    status: LeadStatus
    company_type: str | None = None
    provider: str | None = None
    tags: list[str] | None = None
    created_at: datetime
    gst_number: str | None = None
    lat: float | None = None
    lng: float | None = None
    ai_summary: str | None = None
    # Where the lead came from. `source_provider` names the specific source
    # ("Overpass API", "Website Scanner"); `provider` above is only populated
    # when the origin has a catalogue row, so it is null for scanner and import
    # leads and for any provider row that was later deleted.
    source_type: str | None = None
    source_provider: str | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_lead(cls, lead, provider_name: str | None = None) -> "LeadOut":
        company = lead.company
        return cls(
            id=lead.id,
            company=company.name if company else "",
            industry=company.industry if company else None,
            city=company.city if company else None,
            country=company.country if company else None,
            contact_name=lead.contact_name,
            email=lead.email,
            phone=lead.phone,
            website=company.website if company else None,
            rating=float(company.rating) if company and company.rating is not None else None,
            revenue_band=company.revenue_band if company else None,
            lead_score=lead.lead_score,
            status=lead.status,
            company_type=company.company_type if company else None,
            provider=provider_name,
            tags=lead.tags,
            created_at=lead.created_at,
            gst_number=company.gst_number if company else None,
            lat=float(company.lat) if company and company.lat is not None else None,
            lng=float(company.lng) if company and company.lng is not None else None,
            ai_summary=lead.ai_summary,
            source_type=lead.source_type,
            source_provider=lead.source_provider,
        )


class LeadNoteOut(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    author_id: uuid.UUID | None = None
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadActivityOut(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    event_type: str
    description: str
    extra_data: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadDetailOut(LeadOut):
    notes: list[LeadNoteOut] = Field(default_factory=list)
    activities: list[LeadActivityOut] = Field(default_factory=list)


class LeadCreate(BaseModel):
    company: str = Field(min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=150)
    company_type: str | None = Field(default=None, max_length=100)
    revenue_band: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=255)
    gst_number: str | None = Field(default=None, max_length=32)
    city: str | None = Field(default=None, max_length=150)
    country: str | None = Field(default=None, max_length=150)
    lat: float | None = None
    lng: float | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    contact_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    lead_score: int = Field(default=0, ge=0, le=100)
    status: LeadStatus = LeadStatus.NEW
    tags: list[str] | None = None
    ai_summary: str | None = None


class LeadUpdate(BaseModel):
    status: LeadStatus | None = None
    tags: list[str] | None = None
    contact_name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    lead_score: int | None = Field(default=None, ge=0, le=100)
    ai_summary: str | None = None


class LeadNoteCreate(BaseModel):
    text: str = Field(min_length=1)


class BulkDeleteRequest(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1)


SortOrder = Literal["asc", "desc"]


class CsvImportRowError(BaseModel):
    """One rejected or partially-accepted CSV row, with its spreadsheet line."""

    line: int
    message: str
    company: str | None = None


class CsvImportResult(BaseModel):
    """Summary returned by POST /leads/import."""

    total_rows: int
    imported: int
    duplicates_skipped: int
    invalid_rows: int
    errors: list[CsvImportRowError] = Field(default_factory=list)
    dedup_signals: dict[str, int] = Field(default_factory=dict)


# --- Contact enrichment ---------------------------------------------------


class EnrichLeadsRequest(BaseModel):
    """Which leads to enrich.

    `lead_ids` empty with `all_unenriched=true` is the "Enrich All" button: the
    server picks the leads rather than the browser sending thousands of ids.
    """

    lead_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    all_unenriched: bool = False
    # Bounds "Enrich All" so one click cannot start an unbounded run.
    limit: int = Field(default=50, ge=1, le=500)


class EnrichmentOutcomeOut(BaseModel):
    lead_id: uuid.UUID
    status: str
    website: str | None = None
    website_confidence: int | None = None
    fields_added: list[str] = Field(default_factory=list)
    # field name -> page URL the value was read from.
    field_sources: dict[str, str] = Field(default_factory=dict)
    error: str | None = None


class EnrichmentSummaryOut(BaseModel):
    """Exactly the counters the bulk UI shows."""

    total: int
    processed: int
    website_found: int
    phone_found: int
    email_found: int
    gst_found: int
    social_found: int
    no_website: int
    failed: int
    credits_charged: int
    # False when Google Places has no key: the UI explains why discovery found
    # nothing instead of implying the businesses have no websites.
    discovery_available: bool
    results: list[EnrichmentOutcomeOut] = Field(default_factory=list)
