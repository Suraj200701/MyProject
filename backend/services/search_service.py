"""Lead search orchestration and the website scanner — real data only.

All placeholder/synthetic lead generation has been removed. Every lead
persisted by this module originates from a real source:

  * **Google Places API (New)** — `services/providers/google_places.py`
  * **Mappls (MapmyIndia)** — `services/providers/mappls.py`
  * **Bing Web Search** — `services/providers/bing_search.py`
  * **Company Website Search** — `services/providers/website_search.py`
    (real crawl, no paid API)
  * **CSV import** and **manual entry** — `services/lead_import.py`,
    `POST /leads`

Pipeline
--------
    resolve configured providers
      -> reserve credits (402 if the balance can't cover the worst case)
      -> query providers concurrently, isolating per-provider failures
      -> deduplicate (GSTIN -> domain -> phone -> name+city)
      -> score (LLM when configured, signal-based otherwise)
      -> persist Company/Lead rows
      -> settle credits against what was actually produced

Behaviour when nothing is configured
------------------------------------
A search with no configured provider completes with `results_count = 0` and one
`SearchProviderRun` per provider carrying a real reason (SKIPPED/FAILED). It
does **not** fabricate leads, and it does not consume credits, because
unconfigured providers are excluded before the reservation is calculated. The
API contract is unchanged — callers still get a 201 and a `SearchOut`.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.enums import LeadSourceType, SearchMode, SearchStatus
from models.lead import Company, Lead
from models.search import ApiProvider, Search, SearchProviderRun, WebsiteScan
from schemas.search import SearchCreate, WebsiteScanCreate
from services import usage_service
from services.enrichment import dedup, scoring
from services.enrichment import extractors
from services.providers.base import (
    NormalizedLead,
    ProviderRunStatus,
    ProviderSearchResult,
    SearchQuery,
)
from services.providers.registry import resolve_lead_providers
from services.providers.website_search import build_website_profile
from services.safe_http import FetchError
from utils.exceptions import BadRequestError
from utils.url_guard import resolve_and_validate

logger = logging.getLogger("leadmaster.search")

# Recorded on a scan-saved lead as `source_provider`, alongside
# `source_type = "scanner"`.
#
# It is not a `provider_id`: that column points at `api_providers`, the scanner
# has no row there, and inventing one would put a non-provider card in the API
# Manager grid. `source_provider` is a free-text label precisely so origins
# without a catalogue row can still name themselves.
SCANNER_SOURCE = "Website Scanner"

# Providers that serve public map data: open licence, no credential, no API key.
# This is the set Map Mode draws on.
#
# Membership is by capability, not by "has no credential": Company Website Search
# also needs no credential, but it crawls company websites rather than reading a
# public map, so it belongs with the API sources. Getting that wrong would make
# Map Mode quietly start crawling third-party sites.
MAP_PROVIDER_NAMES = frozenset({"OpenStreetMap", "Overpass API"})


def _partition_by_source(resolved):
    """Splits resolved providers into (map, api) by `MAP_PROVIDER_NAMES`."""
    map_side = [(row, adapter) for row, adapter in resolved if row.name in MAP_PROVIDER_NAMES]
    api_side = [(row, adapter) for row, adapter in resolved if row.name not in MAP_PROVIDER_NAMES]
    return map_side, api_side


def _source_type_for(provider_name: str | None) -> str:
    """Which origin label a lead from this provider gets."""
    if provider_name in MAP_PROVIDER_NAMES:
        return LeadSourceType.MAP.value
    return LeadSourceType.API.value


# Provider-run status mapping. SKIPPED is its own state: a provider without
# credentials never ran, and reporting that as FAILED made every search look
# like several broken integrations (see migration 3a6fd6f68951).
_RUN_STATUS = {
    ProviderRunStatus.COMPLETED: SearchStatus.COMPLETED,
    ProviderRunStatus.FAILED: SearchStatus.FAILED,
    ProviderRunStatus.SKIPPED: SearchStatus.SKIPPED,
}


async def run_search(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SearchCreate,
    *,
    metering_exempt: bool = False,
) -> Search:
    """Runs a metered, deduplicated, scored search across configured providers.

    `metering_exempt` comes from `usage_service.is_metering_exempt(user)` at the
    route layer, where the authenticated `User` is available. When set, no
    balance check happens and no credits are debited — see that helper for who
    qualifies and why.
    """
    # Every catalogue row is a candidate; `resolve_lead_providers` is the single
    # authority on which ones can actually run (it decrypts credentials and drops
    # anything unconfigured or without an adapter).
    #
    # This deliberately does NOT filter on `ApiProvider.connected`. That column
    # records "this workspace stored its own credentials", which the API Manager
    # grid displays — it is not a routing switch, and nothing in the UI can set
    # it independently. Using it as a filter meant that the moment one provider
    # got workspace credentials, every provider configured through `.env` was
    # silently excluded from search: a newly added key would appear configured,
    # test green, and still never be queried.
    provider_rows = list((await db.execute(select(ApiProvider))).scalars().all())

    all_resolved = resolve_lead_providers(provider_rows)
    map_resolved, api_resolved = _partition_by_source(all_resolved)

    # Which sources this run is allowed to use.
    #
    # `mode is None` keeps the pre-Lead-Source behaviour — every configured
    # provider at once — so API clients that never heard of modes are unaffected.
    mode = data.mode
    if mode is SearchMode.MAP:
        resolved = map_resolved
    elif mode is SearchMode.API:
        resolved = api_resolved
    elif mode is SearchMode.AUTO:
        # Auto runs the API side first and only falls back below, so it starts
        # with the API set. The reservation still has to cover the fallback.
        resolved = api_resolved
    else:
        resolved = all_resolved

    unconfigured = [row for row in provider_rows if row.name not in {r.name for r, _ in resolved}]

    # Only providers this mode can actually call are reserved for. Auto also
    # reserves the map side, because the fallback may run: over-reserving is
    # refunded at settle time, whereas under-reserving would let a search start
    # work it cannot pay for.
    reservable = [row for row, _ in resolved]
    if mode is SearchMode.AUTO:
        reservable += [row for row, _ in map_resolved]
    estimate = usage_service.estimate_search_cost(reservable)
    reservation = await usage_service.reserve_credits(
        db, organization_id, estimate, f"Lead search: {data.query[:120]}", exempt=metering_exempt
    )

    try:
        search = Search(
            organization_id=organization_id,
            user_id=user_id,
            query=data.query,
            location=data.location,
            filters={"industry": data.industry, "country": data.country},
            status=SearchStatus.RUNNING,
        )
        db.add(search)
        await db.flush()

        query = SearchQuery(
            query=data.query,
            location=data.location,
            industry=data.industry,
            country=data.country,
            max_results=max(1, settings.SEARCH_MAX_RESULTS_PER_PROVIDER),
        )

        results = await _query_providers(resolved, query)

        # Auto mode: fall back to public map data when the API side produced
        # nothing usable.
        #
        # "Nothing usable" is zero leads, not "a provider failed" — a run where
        # Google errored but Mappls returned twelve leads is a success, and
        # spending map calls on top of it would be waste. The fallback also runs
        # when there was no API provider to call at all, which is the common case
        # on a fresh deployment with no keys entered yet.
        if mode is SearchMode.AUTO and not any(result.leads for result in results):
            fallback = await _query_providers(map_resolved, query)
            results.extend(fallback)
            # The map providers really ran, so they join the set that gets a
            # provider_run row and can be billed for what they returned.
            resolved = list(resolved) + list(map_resolved)
            unconfigured = [
                row for row in provider_rows if row.name not in {r.name for r, _ in resolved}
            ]

        # Record every provider that couldn't run, so the UI can explain why a
        # search returned little rather than looking silently broken.
        now = datetime.now(UTC)
        for row in unconfigured:
            db.add(
                SearchProviderRun(
                    search_id=search.id,
                    provider_id=row.id,
                    # Not configured, or not a lead source at all — it never ran.
                    status=SearchStatus.SKIPPED,
                    results_found=0,
                    started_at=now,
                    completed_at=now,
                )
            )

        all_leads: list[NormalizedLead] = []
        provider_by_name = {row.name: row for row, _ in resolved}

        for result in results:
            row = provider_by_name.get(result.provider_name)
            db.add(
                SearchProviderRun(
                    search_id=search.id,
                    provider_id=row.id if row else None,
                    status=_RUN_STATUS[result.status],
                    results_found=result.count,
                    started_at=now,
                    completed_at=datetime.now(UTC),
                )
            )
            if row is not None:
                # Real call counts and latency, only for calls actually made.
                if result.status is not ProviderRunStatus.SKIPPED:
                    row.usage_count += max(1, result.count)
                if result.latency_ms:
                    row.latency_ms = result.latency_ms
            all_leads.extend(result.leads)

        dedup_result = await dedup.deduplicate(db, organization_id, all_leads)
        unique_leads = dedup_result.unique

        scores = await scoring.score_leads(unique_leads, data.industry)

        billable_by_provider: dict[uuid.UUID, int] = {}
        for lead, (score, summary) in zip(unique_leads, scores):
            row = provider_by_name.get(lead.source_provider or "")
            company = await _get_or_create_company(db, lead)
            db.add(
                Lead(
                    organization_id=organization_id,
                    company_id=company.id,
                    contact_name=lead.contact_name,
                    email=lead.email,
                    phone=lead.phone,
                    lead_score=score,
                    status="new",
                    tags=lead.tags or None,
                    provider_id=row.id if row else None,
                    # Provenance that outlives the provider row: `provider_id` is
                    # SET NULL if the catalogue entry is deleted, and the UI needs
                    # to keep showing where the lead came from.
                    source_type=_source_type_for(lead.source_provider),
                    source_provider=lead.source_provider,
                    search_id=search.id,
                    created_by_id=user_id,
                    ai_summary=summary,
                )
            )
            if row is not None:
                billable_by_provider[row.id] = billable_by_provider.get(row.id, 0) + 1

        search.status = SearchStatus.COMPLETED
        search.results_count = len(unique_leads)
        search.completed_at = datetime.now(UTC)

        actual_cost = usage_service.calculate_search_actual_cost(
            billable_by_provider, [row for row, _ in resolved]
        )
        await usage_service.settle_reservation(db, reservation, actual_cost)

        await db.commit()
    except Exception:
        # The reservation is pending in this transaction, so rolling back is
        # itself the refund — calling release_reservation() here would credit
        # the balance twice. (See services/usage_service.release_reservation.)
        await db.rollback()
        raise

    refreshed = (
        await db.execute(
            select(Search).where(Search.id == search.id).execution_options(populate_existing=True)
        )
    ).scalar_one()
    await db.refresh(refreshed, attribute_names=["provider_runs"])
    return refreshed


async def _query_providers(resolved, query: SearchQuery) -> list[ProviderSearchResult]:
    """Queries every provider concurrently, isolating failures.

    `return_exceptions=True` means one adapter raising an unexpected error
    cannot cancel its siblings; it becomes a FAILED run for that provider only.
    """
    if not resolved:
        return []

    async def run_one(row: ApiProvider, adapter) -> ProviderSearchResult:
        try:
            return await adapter.search(query)
        except Exception as exc:  # noqa: BLE001 - defensive isolation boundary
            logger.exception("Provider %s raised unexpectedly", row.name)
            return ProviderSearchResult(
                provider_name=row.name,
                status=ProviderRunStatus.FAILED,
                error=f"Unexpected error: {type(exc).__name__}",
            )

    gathered = await asyncio.gather(
        *(run_one(row, adapter) for row, adapter in resolved), return_exceptions=True
    )

    results: list[ProviderSearchResult] = []
    for (row, _adapter), outcome in zip(resolved, gathered):
        if isinstance(outcome, BaseException):
            results.append(
                ProviderSearchResult(
                    provider_name=row.name,
                    status=ProviderRunStatus.FAILED,
                    error=f"Unexpected error: {type(outcome).__name__}",
                )
            )
        else:
            results.append(outcome)
    return results


async def _get_or_create_company(db: AsyncSession, lead: NormalizedLead) -> Company:
    """Finds an existing company for this lead or creates one.

    Reuses the dedup fingerprint logic so a company matched by domain isn't
    duplicated just because its name is spelled differently this time.
    """
    domain = dedup.normalize_domain(lead.website)
    gstin = (lead.gst_number or "").strip().upper()

    if gstin:
        existing = (
            await db.execute(select(Company).where(Company.gst_number == gstin).limit(1))
        ).scalar_one_or_none()
        if existing is not None:
            _fill_company_gaps(existing, lead)
            return existing

    if domain:
        # The ILIKE is only a candidate *prefilter*; the match is decided by
        # comparing registrable domains. On its own the substring match merges
        # unrelated companies: a lead on `apple.com` matched a stored
        # `https://notapple.com`, and `apple.com.evil.net` — a different site
        # entirely, registrable domain `evil.net` — matched too. Comparing
        # through `normalize_domain` is also what dedup does, so a company
        # matched here and a lead deduplicated there agree.
        candidates = (
            await db.execute(select(Company).where(Company.website.ilike(f"%{domain}%")).limit(50))
        ).scalars().all()
        for candidate in candidates:
            if dedup.normalize_domain(candidate.website) == domain:
                _fill_company_gaps(candidate, lead)
                return candidate

    normalized_city = dedup.normalize_city(lead.city)
    if lead.company_name and normalized_city:
        candidates = (
            await db.execute(
                select(Company).where(Company.city.ilike(f"%{normalized_city}%")).limit(200)
            )
        ).scalars().all()
        target = dedup.normalize_company_name(lead.company_name)
        for candidate in candidates:
            if dedup.name_similarity(target, dedup.normalize_company_name(candidate.name)) >= (
                settings.DEDUP_NAME_SIMILARITY_THRESHOLD
            ):
                _fill_company_gaps(candidate, lead)
                return candidate

    company = Company(
        name=lead.company_name,
        industry=lead.industry,
        company_type=lead.company_type,
        revenue_band=lead.revenue_band,
        website=lead.website,
        gst_number=gstin or None,
        address=lead.address,
        city=lead.city,
        country=lead.country,
        lat=lead.lat,
        lng=lead.lng,
        rating=lead.rating,
    )
    db.add(company)
    await db.flush()
    return company


def _fill_company_gaps(company: Company, lead: NormalizedLead) -> None:
    """Enriches an existing company with fields it is missing. Never overwrites."""
    for company_attr, lead_attr in (
        ("industry", "industry"),
        ("company_type", "company_type"),
        ("revenue_band", "revenue_band"),
        ("website", "website"),
        ("gst_number", "gst_number"),
        ("address", "address"),
        ("city", "city"),
        ("country", "country"),
        ("lat", "lat"),
        ("lng", "lng"),
        ("rating", "rating"),
    ):
        if getattr(company, company_attr, None) in (None, "") and getattr(lead, lead_attr, None) not in (None, ""):
            setattr(company, company_attr, getattr(lead, lead_attr))


async def save_scan_as_lead(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    scan: WebsiteScan,
) -> tuple[Lead, bool]:
    """Turns a completed website scan into a lead.

    Returns `(lead, created)` — `created=False` when this scan was already saved,
    which makes the endpoint idempotent: clicking "Save to Lead" twice must not
    produce two leads. `WebsiteScan.lead_id` records the link (the column existed
    for exactly this and was never written).

    The scan's findings go through the **same** dedup -> score -> persist path as
    any provider result, so a scanned company that already exists is merged rather
    than duplicated, and the lead gets a real AI score instead of the scan's
    confidence number (which measures extraction quality, not lead quality).
    """
    if scan.lead_id is not None:
        existing = (
            await db.execute(select(Lead).where(Lead.id == scan.lead_id))
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False

    if not scan.company_name and not scan.domain:
        raise BadRequestError(
            "This scan found no company name or domain, so there is nothing to save as a lead."
        )

    social = scan.social_links or {}
    lead = NormalizedLead(
        # A failed scan still has its domain; that is a better name than nothing.
        company_name=scan.company_name or scan.domain,
        website=scan.url,
        gst_number=scan.gst_number if scan.gst_verified else None,
        contact_name=scan.contact_person,
        email=(scan.emails or [None])[0],
        phone=(scan.phones or [None])[0],
        tags=["Website Scan"],
        raw={
            "source": "Website Scanner",
            "scan_id": str(scan.id),
            "domain": scan.domain,
            "confidence_score": scan.confidence_score,
            "emails": scan.emails or None,
            "phones": scan.phones or None,
            "social_links": social or None,
            "ssl_valid": scan.ssl_valid,
            "mobile_friendly": scan.mobile_friendly,
            "seo_score": scan.seo_score,
        },
        source_provider=SCANNER_SOURCE,
    )

    dedup_result = await dedup.deduplicate(db, organization_id, [lead])
    if not dedup_result.unique:
        # Already in the database under a different name/spelling. Link the scan to
        # the lead it matched rather than reporting success with nothing to show.
        # `existing_matches` pairs each dropped lead with the id it matched —
        # exactly the case its docstring anticipates.
        matched_id = (
            dedup_result.existing_matches[0][1] if dedup_result.existing_matches else None
        )
        if matched_id is not None:
            matched = (
                await db.execute(select(Lead).where(Lead.id == matched_id))
            ).scalar_one_or_none()
            if matched is not None:
                scan.lead_id = matched.id
                await db.commit()
                return matched, False
        raise BadRequestError("This company is already in your lead database.")

    unique_lead = dedup_result.unique[0]
    scores = await scoring.score_leads([unique_lead])
    score, summary = scores[0] if scores else (scoring.score_lead_by_signals(unique_lead), "")

    company = await _get_or_create_company(db, unique_lead)
    row = Lead(
        organization_id=organization_id,
        company_id=company.id,
        contact_name=unique_lead.contact_name,
        email=unique_lead.email,
        phone=unique_lead.phone,
        lead_score=score,
        status="new",
        tags=unique_lead.tags or None,
        source_type=LeadSourceType.SCANNER.value,
        source_provider=SCANNER_SOURCE,
        created_by_id=user_id,
        ai_summary=summary,
    )
    db.add(row)
    await db.flush()

    scan.lead_id = row.id
    await db.commit()
    await db.refresh(row)

    logger.info("Saved scan %s of %s as lead %s", scan.id, scan.domain, row.id)
    return row, True


# --- Website scanner -----------------------------------------------------


async def scan_website(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    data: WebsiteScanCreate,
    *,
    metering_exempt: bool = False,
) -> WebsiteScan:
    """Scans a real website: validates, fetches, and extracts actual content.

    Ordering: SSRF validation first (an unsafe URL costs nothing and creates no
    rows), then credit reservation, then the fetch. A site that is unreachable
    still produces a persisted `WebsiteScan` row recording the failure — the
    scan genuinely happened and consumed a credit, so hiding it would be wrong.
    """
    validated = await resolve_and_validate(data.url)

    reservation = await usage_service.reserve_credits(
        db,
        organization_id,
        usage_service.scan_cost(),
        f"Website scan: {validated.hostname}",
        exempt=metering_exempt,
    )

    try:
        started = time.perf_counter()
        try:
            profile = await build_website_profile(validated.url)
        except FetchError as exc:
            profile = None
            fetch_error = str(exc)
        else:
            fetch_error = profile.error

        duration_ms = int((time.perf_counter() - started) * 1000)

        if profile is None or not profile.succeeded:
            scan = WebsiteScan(
                organization_id=organization_id,
                user_id=user_id,
                url=validated.url,
                domain=validated.hostname,
                company_name=None,
                contact_person=None,
                confidence_score=0,
                emails=None,
                phones=None,
                gst_number=None,
                gst_verified=False,
                social_links=extractors.extract_social_links(""),
                ssl_valid=False,
                mobile_friendly=False,
                load_time_ms=profile.load_time_ms if profile else None,
                seo_score=None,
                scan_duration_ms=duration_ms,
            )
            db.add(scan)
            logger.info("Scan of %s failed: %s", validated.hostname, fetch_error)
        else:
            scan = WebsiteScan(
                organization_id=organization_id,
                user_id=user_id,
                url=profile.url,
                domain=profile.domain or validated.hostname,
                company_name=profile.company_name,
                contact_person=None,  # requires a people-data source; not fabricated
                confidence_score=_confidence_from_profile(profile),
                emails=profile.emails or None,
                phones=profile.phones or None,
                gst_number=profile.gstin,
                gst_verified=bool(profile.gstin),  # only checksum-valid GSTINs reach here
                social_links=profile.social_links,
                ssl_valid=profile.ssl_valid,
                mobile_friendly=profile.mobile_friendly,
                load_time_ms=profile.load_time_ms,
                seo_score=profile.seo_score,
                scan_duration_ms=duration_ms,
            )
            db.add(scan)
            if profile.gstin_rejected:
                # Visible rather than silent: a GST format change should look
                # like a bug report, not like "this site has no GST".
                logger.info(
                    "Scan of %s found %s GSTIN-shaped string(s) failing checksum: %s",
                    profile.domain,
                    len(profile.gstin_rejected),
                    profile.gstin_rejected[:3],
                )

        await usage_service.settle_reservation(db, reservation, usage_service.scan_cost())
        await db.commit()
        await db.refresh(scan)
        return scan
    except Exception:
        await db.rollback()
        raise


def _confidence_from_profile(profile) -> int:
    """Confidence derived from what was actually found on the page.

    Replaces the previous random figure. Weighted by how directly each signal
    supports "this is a contactable, legitimate business".
    """
    score = 0
    if profile.emails:
        score += 30
    if profile.phones:
        score += 22
    if profile.gstin:
        score += 18  # checksum-verified registration
    if profile.ssl_valid:
        score += 8
    if profile.mobile_friendly:
        score += 5
    found_social = sum(1 for s in profile.social_links if s.get("found"))
    score += min(10, found_social * 3)
    score += int(7 * (profile.seo_score / 100)) if profile.seo_score else 0
    return max(1, min(100, score))
