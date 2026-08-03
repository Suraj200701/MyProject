"""Lead-provider abstraction.

Every lead source — a paid API, a website crawl, a CSV file, or a human typing
into a form — produces `NormalizedLead` values. Downstream stages
(deduplication, scoring, persistence) therefore work identically no matter
where a lead came from, and adding a source means writing one adapter rather
than touching the search pipeline.

Contract for adapters
---------------------
* `search()` must never raise for an expected failure (missing credentials,
  quota exhausted, provider 5xx). It returns `ProviderSearchResult` with
  `status=FAILED` and a human-readable `error`, so one broken provider degrades
  a multi-provider search instead of failing it. Genuinely unexpected errors
  may propagate.
* `is_configured` decides whether the provider is offered at all. A provider
  without credentials is skipped rather than attempted, so users are never
  charged credits for a call that cannot succeed.
* Adapters must respect `max_results` — it is the cost ceiling that credit
  metering reserves against.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

logger = logging.getLogger("leadmaster.providers")


class ProviderRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NormalizedLead:
    """A single lead candidate in provider-independent form.

    Only `company_name` is required — real sources are patchy, and demanding
    more would mean discarding usable leads or inventing values to fill gaps.
    """

    company_name: str
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
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    tags: list[str] = field(default_factory=list)
    # Verbatim provider payload, kept for debugging and for re-parsing if an
    # extraction rule improves later. Never surfaced through the API.
    raw: dict = field(default_factory=dict)
    source_provider: str | None = None

    def __post_init__(self) -> None:
        self.company_name = (self.company_name or "").strip()[:255]
        if self.website:
            self.website = self.website.strip()[:255]
        if self.city:
            self.city = self.city.strip()[:150]
        if self.country:
            self.country = self.country.strip()[:150]
        # Providers report ratings on different scales; clamp to the 0-5 the
        # schema (Numeric(2,1)) and the frontend's star display expect.
        if self.rating is not None:
            self.rating = max(0.0, min(5.0, round(float(self.rating), 1)))


@dataclass
class ProviderSearchResult:
    """Outcome of querying one provider."""

    provider_name: str
    status: ProviderRunStatus
    leads: list[NormalizedLead] = field(default_factory=list)
    error: str | None = None
    latency_ms: int = 0

    @property
    def count(self) -> int:
        return len(self.leads)


@dataclass
class SearchQuery:
    """Normalized search input handed to every adapter."""

    query: str
    location: str | None = None
    industry: str | None = None
    country: str | None = None
    max_results: int = 5

    @property
    def full_text(self) -> str:
        """Provider-ready free-text query combining the terms we were given."""
        parts = [self.query]
        if self.industry and self.industry.lower() not in self.query.lower():
            parts.append(self.industry)
        if self.location and self.location.lower() not in self.query.lower():
            parts.append(f"in {self.location}")
        return " ".join(p for p in parts if p).strip()


@runtime_checkable
class LeadProvider(Protocol):
    """Interface every lead source implements."""

    name: str

    @property
    def is_configured(self) -> bool:
        """False when required credentials are absent."""
        ...

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        """Runs the provider's search. Must not raise on expected failures."""
        ...


def skipped(provider_name: str, reason: str) -> ProviderSearchResult:
    """Helper for 'not configured / not applicable' outcomes."""
    return ProviderSearchResult(
        provider_name=provider_name,
        status=ProviderRunStatus.SKIPPED,
        error=reason,
    )


def failed(provider_name: str, reason: str, latency_ms: int = 0) -> ProviderSearchResult:
    """Helper for a genuine provider failure."""
    logger.warning("Provider %s failed: %s", provider_name, reason)
    return ProviderSearchResult(
        provider_name=provider_name,
        status=ProviderRunStatus.FAILED,
        error=reason[:500],
        latency_ms=latency_ms,
    )
