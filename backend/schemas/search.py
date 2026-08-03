"""Pydantic schemas for lead search, API providers, and website scans."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from models.enums import ProviderCategory, ProviderStatus, SearchStatus


class SearchCreate(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    location: str | None = None
    industry: str | None = None
    country: str | None = None


class ProviderRunOut(BaseModel):
    provider_id: uuid.UUID
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
