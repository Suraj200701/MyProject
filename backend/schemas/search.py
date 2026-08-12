"""Pydantic schemas for lead search, API providers, and website scans."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from models.enums import ProviderCategory, ProviderStatus, SearchMode, SearchStatus


class SearchCreate(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    location: str | None = None
    industry: str | None = None
    country: str | None = None
    # Which sources to use. Optional on purpose: omitting it queries every
    # configured provider, which is exactly how search behaved before Lead Source
    # existed, so older clients and integrations are unaffected.
    mode: SearchMode | None = None


class ProviderRunOut(BaseModel):
    # Optional because not every source has a catalogue row. The Google Maps
    # Extractor runs through the Places credential rather than its own
    # `api_providers` entry, and `run_search` already passes None for a run it
    # cannot match back to a row — the schema just used to reject it.
    provider_id: uuid.UUID | None = None
    provider_name: str
    status: SearchStatus
    results_found: int

    model_config = {"from_attributes": True}


class SearchOut(BaseModel):
    id: uuid.UUID
    query: str
    location: str | None = None
    status: SearchStatus
    results_count: int
    created_at: datetime
    completed_at: datetime | None = None
    provider_runs: list[ProviderRunOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ApiProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    category: ProviderCategory
    status: ProviderStatus
    logo: str | None = None
    description: str | None = None
    usage_count: int
    usage_limit: int
    latency_ms: int
    connected: bool

    model_config = {"from_attributes": True}


class WebsiteScanCreate(BaseModel):
    url: str = Field(min_length=3, max_length=500)


class SocialLinkResult(BaseModel):
    platform: str
    found: bool
    handle: str | None = None


class WebsiteScanOut(BaseModel):
    id: uuid.UUID
    url: str
    domain: str
    company_name: str | None = None
    contact_person: str | None = None
    confidence_score: int
    emails: list[str] | None = None
    phones: list[str] | None = None
    gst_number: str | None = None
    gst_verified: bool
    social_links: list[SocialLinkResult] | None = None
    ssl_valid: bool
    mobile_friendly: bool
    load_time_ms: int | None = None
    seo_score: int | None = None
    scan_duration_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProviderCredentialFieldOut(BaseModel):
    """Describes one credential input, so the UI doesn't hardcode labels."""

    label: str
    env_var: str
    is_set: bool


class ProviderCredentialStatusOut(BaseModel):
    """Whether a provider has credentials — never the credentials themselves.

    `source` says which value the search pipeline will actually use:
      * `workspace`     — the encrypted values stored on this provider row
      * `environment`   — the platform-wide `.env` values
      * `unset`         — nothing configured; the provider is skipped
      * `none_required` — this provider needs no credentials
    """

    provider_id: uuid.UUID
    name: str
    source: Literal["workspace", "environment", "unset", "none_required"]
    key: ProviderCredentialFieldOut | None = None
    secret: ProviderCredentialFieldOut | None = None
    help_url: str | None = None


class ProviderCredentialUpdate(BaseModel):
    """Write-only. Omit a field to leave the stored value untouched.

    Values are encrypted before storage and are never returned by any endpoint.
    """

    api_key: str | None = Field(default=None, min_length=1, max_length=1000)
    api_secret: str | None = Field(default=None, min_length=1, max_length=1000)


class ProviderTestResult(BaseModel):
    """Outcome of a real connectivity/authentication test.

    Returned with HTTP 200 even when `success` is false: the API call worked, it
    is the *provider* that rejected us, and a non-2xx here could not be told
    apart from this endpoint being broken. `details` carries the provider's
    status code, error body and exception; the traceback stays in the server log.
    """

    provider: str
    success: bool
    authenticated: bool
    message: str
    latency_ms: int
    details: dict = Field(default_factory=dict)


# --- Map Mode -------------------------------------------------------------


class MapViewport(BaseModel):
    """The map rectangle currently on screen.

    Sent when the user pans or zooms: Places `searchText` takes this as a
    `locationRestriction`, so "collect what is visible now" is one more API call
    rather than anything read off the rendered map.
    """

    south: float = Field(ge=-90, le=90)
    west: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)


class MapExtractRequest(BaseModel):
    """Keyword + location for a public map extraction."""

    query: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    # Overpass needs a spatial filter; the bounds match the adapter's clamp.
    radius_km: float | None = Field(default=None, ge=1, le=100)
    max_results: int | None = Field(default=None, ge=1, le=200)
    # Which source to collect from. "osm" keeps the previous behaviour and stays
    # the default, so existing callers are unaffected.
    source: Literal["osm", "google_maps"] = "osm"
    # Extra keywords run as separate searches. Places ranks one blended query
    # rather than unioning terms, so "panel, control panel" as a single string
    # returns fewer distinct businesses than the two run apart.
    extra_keywords: list[str] = Field(default_factory=list, max_length=10)
    viewport: MapViewport | None = None


class MapResultOut(BaseModel):
    """One publicly available business, as rendered on the map.

    Every field is nullable because OSM is volunteer-mapped and most POIs carry
    only a name and a position. Absent data stays absent — nothing here is
    inferred or filled in.
    """

    id: str
    company_name: str | None = None
    category: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    source_provider: str | None = None
    osm_url: str | None = None


class MapExtractResponse(BaseModel):
    results: list[MapResultOut]
    provider_runs: list[ProviderRunOut]
    # Set when the run returned nothing *because a provider refused or timed
    # out*, so the UI can offer a retry rather than claiming the area is empty.
    blocked_reason: str | None = None


class MapImportRequest(BaseModel):
    """The subset of extracted results the user chose to keep."""

    results: list[MapResultOut] = Field(min_length=1, max_length=500)


class MapImportResponse(BaseModel):
    imported: int
    duplicates: int
    lead_ids: list[uuid.UUID]
