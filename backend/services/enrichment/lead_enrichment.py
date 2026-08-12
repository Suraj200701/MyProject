"""Turn a sparse map-sourced lead into a useful one, from public data only.

    lead (name + address)
      -> already has a website?  skip discovery
      -> else Google Places (optional) -> verified websiteUri
      -> crawl the site with the existing build_website_profile
      -> merge phone / email / GSTIN / socials, never downgrading
      -> record where every value came from
      -> ENRICHED | NO_WEBSITE_FOUND | FAILED

Nothing here fetches anything a signed-out visitor could not. Crawling reuses
`build_website_profile`, which routes every request through the SSRF guard and
enforces the page, byte and timeout budgets already configured for the scanner.

Merging
-------
The rule is *never overwrite stronger data with weaker*. A phone number the
provider gave us outranks one scraped from a footer, because the provider
asserted it about this specific business while the page might be a shared
landlord's number. So existing values win, and enrichment fills gaps. The
exception is spelled out in `_merge_value`.

Credits
-------
Charged once per lead that actually performed outbound work, and never for a
lead that was skipped, served from cache, or failed before doing anything. The
existing reserve/settle path does the accounting, so the "no charge for work not
done" rule is enforced by settling against a real count rather than by a special
case.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.enums import EnrichmentStatus
from models.lead import Company, Lead
from services import usage_service
from services.enrichment.website_discovery import WebsiteDiscovery, is_usable_website
from services.providers.website_search import build_website_profile
from services.safe_http import FetchError
from utils.exceptions import UnsafeUrlError

logger = logging.getLogger("leadmaster.enrichment.lead")

# Bulk runs are bounded so a 100-lead selection cannot open 100 sockets at once.
# Each unit of work is a crawl of several pages, so this is deliberately small.
MAX_CONCURRENCY = 4

# What one lead's enrichment costs, when it actually does outbound work.
CREDITS_PER_ENRICHMENT = 1


@dataclass
class EnrichmentOutcome:
    """What happened to one lead."""

    lead_id: uuid.UUID
    status: str
    website: str | None = None
    website_confidence: int | None = None
    fields_added: list[str] = field(default_factory=list)
    field_sources: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    # True when nothing outbound happened, so nothing is billable.
    skipped: bool = False
    performed_work: bool = False


@dataclass
class BulkEnrichmentSummary:
    """Counts the bulk UI displays."""

    total: int = 0
    processed: int = 0
    website_found: int = 0
    phone_found: int = 0
    email_found: int = 0
    gst_found: int = 0
    social_found: int = 0
    no_website: int = 0
    failed: int = 0
    skipped: int = 0
    credits_charged: int = 0
    results: list[EnrichmentOutcome] = field(default_factory=list)


def _merge_value(existing: str | None, discovered: str | None) -> tuple[str | None, bool]:
    """Returns (value, changed). Existing data wins.

    A provider asserted its value about *this* business; a crawled value came off
    a page that might belong to a group, a landlord or a web agency. So the only
    time enrichment writes is when the field is currently empty.
    """
    if existing and existing.strip():
        return existing, False
    if discovered and str(discovered).strip():
        return str(discovered).strip(), True
    return existing, False


class LeadEnricher:
    """Enriches leads with publicly available contact information."""

    def __init__(self, discovery: WebsiteDiscovery | None = None) -> None:
        self._discovery = discovery or WebsiteDiscovery()

    @property
    def discovery_available(self) -> bool:
        return self._discovery.is_configured

    async def enrich_one(
        self, db: AsyncSession, lead: Lead, company: Company
    ) -> EnrichmentOutcome:
        """Discovers (if needed), crawls, and merges. Never raises for a bad site."""
        outcome = EnrichmentOutcome(lead_id=lead.id, status=EnrichmentStatus.NOT_ATTEMPTED.value)

        website = company.website if is_usable_website(company.website) else None
        confidence: int | None = lead.website_confidence
        website_source: str | None = lead.website_source

        if website is None:
            # Discovery. Optional by design: with no Places key this returns an
            # explanation and we carry on with what we already have.
            lead.enrichment_status = EnrichmentStatus.DISCOVERING.value
            discovered = await self._discovery.discover(
                name=company.name,
                address=company.address,
                city=company.city,
                phone=lead.phone,
                category=company.industry,
            )
            if discovered.searched and not discovered.from_cache:
                outcome.performed_work = True

            if discovered.found:
                website = discovered.website
                confidence = int(round(discovered.confidence * 100))
                website_source = discovered.source
                outcome.status = EnrichmentStatus.WEBSITE_FOUND.value
            else:
                lead.enrichment_status = EnrichmentStatus.NO_WEBSITE_FOUND.value
                lead.enrichment_error = (discovered.error or "No website found.")[:500]
                lead.enriched_at = datetime.now(UTC)
                outcome.status = EnrichmentStatus.NO_WEBSITE_FOUND.value
                outcome.error = lead.enrichment_error
                return outcome

        # Crawl.
        lead.enrichment_status = EnrichmentStatus.ENRICHING.value
        try:
            profile = await build_website_profile(website)
            outcome.performed_work = True
        except (UnsafeUrlError, FetchError) as exc:
            lead.enrichment_status = EnrichmentStatus.FAILED.value
            lead.enrichment_error = str(exc)[:500]
            lead.enriched_at = datetime.now(UTC)
            outcome.status = EnrichmentStatus.FAILED.value
            outcome.error = lead.enrichment_error
            return outcome

        if not profile.succeeded:
            lead.enrichment_status = EnrichmentStatus.FAILED.value
            lead.enrichment_error = (profile.error or f"HTTP {profile.http_status}")[:500]
            lead.enriched_at = datetime.now(UTC)
            outcome.status = EnrichmentStatus.FAILED.value
            outcome.error = lead.enrichment_error
            return outcome

        sources: dict[str, str] = dict(lead.field_sources or {})
        added: list[str] = []

        # The website itself is now confirmed reachable, so record it.
        if not company.website:
            company.website = profile.url
            added.append("website")
        lead.website_confidence = confidence
        lead.website_source = website_source or profile.url

        phone, changed = _merge_value(lead.phone, profile.phones[0] if profile.phones else None)
        if changed:
            lead.phone = phone
            added.append("phone")
            if src := profile.field_sources.get(profile.phones[0]):
                sources["phone"] = src

        email, changed = _merge_value(lead.email, profile.emails[0] if profile.emails else None)
        if changed:
            lead.email = email
            added.append("email")
            if src := profile.field_sources.get(profile.emails[0]):
                sources["email"] = src

        gst, changed = _merge_value(company.gst_number, profile.gstin)
        if changed:
            company.gst_number = gst
            added.append("gst")
            if src := profile.field_sources.get(profile.gstin):
                sources["gst"] = src

        found_socials = {
            link["platform"]: link.get("handle")
            for link in profile.social_links
            if isinstance(link, dict) and link.get("found")
        }
        if found_socials:
            merged = dict(lead.social_profiles or {})
            for platform, handle in found_socials.items():
                if platform not in merged:
                    merged[platform] = handle
                    if src := profile.field_sources.get(f"social:{platform}"):
                        sources[f"social:{platform}"] = src
            if merged != (lead.social_profiles or {}):
                lead.social_profiles = merged
                added.append("social")

        # Additional numbers and addresses the crawl found are deliberately not
        # written anywhere yet. `field_sources` maps a field name to the URL its
        # value came from, and stuffing an alternate *value* in there broke that
        # contract — the UI renders these as clickable source links, so a bare
        # email address in the URL slot produces a dead link. Persisting them
        # properly needs columns that do not exist, which is a schema decision
        # rather than something to smuggle into a provenance map.

        lead.field_sources = sources or None
        lead.enrichment_status = EnrichmentStatus.ENRICHED.value
        lead.enrichment_error = None
        lead.enriched_at = datetime.now(UTC)

        outcome.status = EnrichmentStatus.ENRICHED.value
        outcome.website = company.website
        outcome.website_confidence = lead.website_confidence
        outcome.fields_added = added
        outcome.field_sources = sources
        return outcome

    async def enrich_many(
        self,
        db: AsyncSession,
        organization_id: uuid.UUID,
        lead_ids: list[uuid.UUID],
        *,
        metering_exempt: bool = False,
    ) -> BulkEnrichmentSummary:
        """Enriches a selection with bounded concurrency, then settles credits."""
        rows = (
            await db.execute(
                select(Lead, Company)
                .join(Company, Lead.company_id == Company.id)
                .where(Lead.organization_id == organization_id, Lead.id.in_(lead_ids))
            )
        ).all()

        summary = BulkEnrichmentSummary(total=len(rows))
        if not rows:
            return summary

        # Reserve the worst case; settle below against work actually performed,
        # which is what keeps cached and skipped leads free.
        reservation = await usage_service.reserve_credits(
            db,
            organization_id,
            len(rows) * CREDITS_PER_ENRICHMENT,
            f"Lead enrichment: {len(rows)} lead(s)",
            exempt=metering_exempt,
        )

        try:
            gate = asyncio.Semaphore(MAX_CONCURRENCY)

            async def run(lead: Lead, company: Company) -> EnrichmentOutcome:
                async with gate:
                    try:
                        return await self.enrich_one(db, lead, company)
                    except Exception as exc:  # noqa: BLE001 - one lead must not sink the batch
                        logger.exception("Enrichment crashed for lead %s", lead.id)
                        lead.enrichment_status = EnrichmentStatus.FAILED.value
                        lead.enrichment_error = f"{type(exc).__name__}: {exc}"[:500]
                        return EnrichmentOutcome(
                            lead_id=lead.id,
                            status=EnrichmentStatus.FAILED.value,
                            error=lead.enrichment_error,
                        )

            outcomes = await asyncio.gather(*(run(lead, company) for lead, company in rows))

            billable = 0
            for outcome in outcomes:
                summary.processed += 1
                summary.results.append(outcome)
                if outcome.performed_work:
                    billable += 1
                if outcome.status == EnrichmentStatus.ENRICHED.value:
                    summary.website_found += 1
                    if "phone" in outcome.fields_added:
                        summary.phone_found += 1
                    if "email" in outcome.fields_added:
                        summary.email_found += 1
                    if "gst" in outcome.fields_added:
                        summary.gst_found += 1
                    if "social" in outcome.fields_added:
                        summary.social_found += 1
                elif outcome.status == EnrichmentStatus.NO_WEBSITE_FOUND.value:
                    summary.no_website += 1
                elif outcome.status == EnrichmentStatus.FAILED.value:
                    summary.failed += 1
                if outcome.skipped:
                    summary.skipped += 1

            charge = billable * CREDITS_PER_ENRICHMENT
            await usage_service.settle_reservation(db, reservation, charge)
            summary.credits_charged = 0 if metering_exempt else charge

            await db.commit()
            return summary
        except Exception:
            # The reservation is pending in this transaction, so rolling back is
            # the refund; release_reservation() as well would double-credit.
            await db.rollback()
            raise
