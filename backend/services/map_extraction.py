"""Map Mode — extract public map data, review it, then import what you picked.

Why this exists next to `run_search`
------------------------------------
`POST /search` persists everything it finds in one shot. Map Mode is a review
workflow: the user opens a map, extracts, looks at what came back, ticks the rows
worth keeping, and imports those. So extraction and persistence are two calls.

Where the data comes from
-------------------------
OpenStreetMap (Nominatim) and Overpass, through the same adapters `run_search`
uses. Both publish openly licensed data (ODbL) and permit programmatic access,
which is what makes Map Mode work with no API key and no browser extension.

Nothing here scrapes a map provider's web interface. Reading another provider's
rendered page would mean working around its terms and its anti-bot measures, and
a proxy service does not make that permissible.

Metering
--------
Extraction is not metered: OSM and Overpass are free public services, so a
preview costs nothing to serve and charging for it would be charging for our own
convenience. Credits are settled on **import**, where leads are actually created
— which is what `credit_cost` means ("credits per result sourced").
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.enums import LeadSourceType
from models.lead import Lead
from models.search import ApiProvider
from services import usage_service
from services.enrichment import dedup, scoring
from services.providers.base import (
    NormalizedLead,
    ProviderRunStatus,
    ProviderSearchResult,
    SearchQuery,
)
from services.providers.registry import resolve_lead_providers
from utils.exceptions import BadRequestError

logger = logging.getLogger("leadmaster.map_extraction")

# Kept in step with `search_service.MAP_PROVIDER_NAMES` by importing it, so the
# two definitions of "what counts as a map source" can never drift apart.
from services.search_service import MAP_PROVIDER_NAMES, _query_providers  # noqa: E402

MIN_RADIUS_KM = 1.0
MAX_RADIUS_KM = 100.0
DEFAULT_RADIUS_KM = 25.0


@dataclass
class MapExtraction:
    """One extraction run: what was found, and what each provider did."""

    results: list[NormalizedLead] = field(default_factory=list)
    provider_runs: list[ProviderSearchResult] = field(default_factory=list)

    @property
    def blocked_reason(self) -> str | None:
        """Why the run produced nothing, when the cause is worth surfacing.

        Distinguishes "the provider refused or timed out" from "the area genuinely
        has no matches" — the first is retryable and the second is not, and
        showing the same empty state for both is what makes an app feel broken.
        """
        if self.results:
            return None
        failures = [r for r in self.provider_runs if r.error and r.status.value == "failed"]
        if failures:
            return failures[0].error
        return None


async def extract_google_maps(
    *,
    keywords: list[str],
    location: str | None,
    viewport=None,
    max_results: int | None = None,
) -> MapExtraction:
    """Google Maps Extractor: official Places API, optionally viewport-scoped.

    Returned as a `MapExtraction` so it flows through exactly the same review and
    import path as the OSM source — same dedup, scoring, persistence and export.
    """
    from services.providers.google_places_extractor import GoogleMapsExtractor

    extractor = GoogleMapsExtractor()
    if not extractor.is_configured:
        raise BadRequestError(
            "Google Places is not configured. Add GOOGLE_MAPS_API_KEY, or use the "
            "OpenStreetMap source, which needs no key."
        )

    leads, errors = await extractor.collect(
        keywords=keywords,
        location=location,
        viewport=viewport,
        max_results=max_results or 20,
    )
    run = ProviderSearchResult(
        provider_name=extractor.name,
        status=ProviderRunStatus.COMPLETED if leads or not errors else ProviderRunStatus.FAILED,
        leads=leads,
        error="; ".join(errors)[:500] if errors else None,
    )
    return MapExtraction(results=leads, provider_runs=[run])


async def extract(
    db: AsyncSession,
    *,
    query: str,
    location: str | None,
    radius_km: float | None = None,
    max_results: int | None = None,
) -> MapExtraction:
    """Runs the public map providers and returns results without persisting."""
    if not query.strip():
        raise BadRequestError("Enter a keyword to extract map results.")

    provider_rows = list((await db.execute(select(ApiProvider))).scalars().all())
    resolved = [
        (row, adapter)
        for row, adapter in resolve_lead_providers(provider_rows)
        if row.name in MAP_PROVIDER_NAMES
    ]
    if not resolved:
        raise BadRequestError(
            "No public map provider is available. OpenStreetMap and Overpass need "
            "no API key — check that they are present in the provider catalogue."
        )

    radius = radius_km if radius_km is not None else DEFAULT_RADIUS_KM
    radius = max(MIN_RADIUS_KM, min(MAX_RADIUS_KM, radius))

    search_query = SearchQuery(
        query=query,
        location=location,
        max_results=max(1, max_results or settings.SEARCH_MAX_RESULTS_PER_PROVIDER),
        radius_km=radius,
    )

    runs = await _query_providers(resolved, search_query)

    # Merge provider outputs and drop within-batch duplicates before the user
    # ever sees them: the same café is frequently both a Nominatim hit and an
    # Overpass node, and asking someone to deduplicate that by hand is rude.
    merged: list[NormalizedLead] = []
    seen: set[tuple] = set()
    for run in runs:
        for lead in run.leads:
            fingerprint = (
                dedup.normalize_domain(lead.website) or "",
                dedup.normalize_phone_key(lead.phone) or "",
                dedup.normalize_company_name(lead.company_name or ""),
                # Coordinates rounded to ~11 m: the same POI mapped twice rarely
                # lands on identical decimals.
                round(lead.lat, 4) if lead.lat is not None else None,
                round(lead.lng, 4) if lead.lng is not None else None,
            )
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            merged.append(lead)

    logger.info(
        "Map extraction for %r near %r: %d results from %d providers",
        query,
        location,
        len(merged),
        len(resolved),
    )
    return MapExtraction(results=merged, provider_runs=runs)


@dataclass
class MapImport:
    """Outcome of importing a selection."""

    imported: int = 0
    duplicates: int = 0
    lead_ids: list[uuid.UUID] = field(default_factory=list)


async def import_results(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    leads: list[NormalizedLead],
    *,
    metering_exempt: bool = False,
) -> MapImport:
    """Persists selected map results through the standard lead pipeline.

    Same path as a provider search — deduplicate, score, then write Company and
    Lead rows — so a map-sourced lead is indistinguishable downstream from any
    other, and the existing lead table and exports work on it unchanged.

    The caller hands back results it received from `extract`. They are re-validated
    by the request schema rather than trusted, but note the trust boundary is
    narrow either way: the worst a caller can do is insert rows into *their own*
    workspace, which `POST /leads` already allows by design.
    """
    if not leads:
        raise BadRequestError("Select at least one result to import.")

    provider_rows = list((await db.execute(select(ApiProvider))).scalars().all())
    row_by_name = {row.name: row for row in provider_rows}

    estimate = usage_service.estimate_search_cost(
        [row for name, row in row_by_name.items() if name in MAP_PROVIDER_NAMES],
        max_results_per_provider=len(leads),
    )
    reservation = await usage_service.reserve_credits(
        db, organization_id, estimate, f"Map import: {len(leads)} result(s)", exempt=metering_exempt
    )

    try:
        # Import the search service lazily: it imports this module's sibling
        # helpers, and a module-level import in both directions would cycle.
        from services.search_service import _get_or_create_company

        dedup_result = await dedup.deduplicate(db, organization_id, leads)
        unique = dedup_result.unique
        duplicates = len(leads) - len(unique)

        scores = await scoring.score_leads(unique)
        billable: dict[uuid.UUID, int] = {}
        created: list[Lead] = []

        for lead, (score, summary) in zip(unique, scores):
            provider_row = row_by_name.get(lead.source_provider or "")
            company = await _get_or_create_company(db, lead)
            row = Lead(
                organization_id=organization_id,
                company_id=company.id,
                contact_name=lead.contact_name,
                email=lead.email,
                phone=lead.phone,
                lead_score=score,
                status="new",
                tags=lead.tags or None,
                provider_id=provider_row.id if provider_row else None,
                source_type=LeadSourceType.MAP.value,
                source_provider=lead.source_provider,
                created_by_id=user_id,
                ai_summary=summary,
            )
            db.add(row)
            created.append(row)
            if provider_row is not None:
                billable[provider_row.id] = billable.get(provider_row.id, 0) + 1

        await db.flush()

        actual = usage_service.calculate_search_actual_cost(billable, provider_rows)
        await usage_service.settle_reservation(db, reservation, actual)
        await db.commit()

        return MapImport(
            imported=len(created),
            duplicates=duplicates,
            lead_ids=[row.id for row in created],
        )
    except Exception:
        # The reservation is pending in this transaction, so the rollback is the
        # refund. See usage_service.release_reservation for why not to also call it.
        await db.rollback()
        raise
