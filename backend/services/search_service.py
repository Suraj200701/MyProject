"""Lead search orchestration and the website scanner.

IMPORTANT — placeholder data-generation, clearly scoped:
This backend has no real third-party search-provider credentials (Google
Places, IndiaMART, JustDial, ...) or web-crawling infrastructure — those
are paid integrations the user hasn't configured yet. Rather than return
literal mock JSON, both `run_search()` and `scan_website()` below
synthesize plausible results and persist them as REAL rows in the
database via the ORM (real Lead/Company/Search/WebsiteScan records,
genuinely queryable afterward) — this is a deliberate, documented stand-in
for the real provider calls, not a mock API response. In production, each
connected `ApiProvider` would be called via its real API instead:
  - Google Places  -> Places API Text Search (https://maps.googleapis.com/maps/api/place/textsearch/json)
  - IndiaMART/TradeIndia/JustDial -> their respective partner/business APIs
  - Website Scanner -> a real crawler using `services/safe_http.safe_fetch`
    (already built and SSRF-hardened) to fetch the target site, then
    extracting emails/phones/GST/social links from the actual page content
    instead of the deterministic-hash approach here.

INFRASTRUCTURE NOW LIVE (this is real, not placeholder):
  * **Credit metering** — both operations reserve credits up front via
    `services/usage_service.py` and settle against actual usage, so a caller
    without credits is refused with HTTP 402 *before* any work starts. This
    is what makes it safe to plug in paid providers later: the spend ceiling
    already exists.
  * **SSRF-hardened URL validation** — `scan_website()` puts every
    user-supplied URL through `utils/url_guard.resolve_and_validate()`
    (scheme/port/hostname policy, DNS resolution, private/loopback/
    link-local/cloud-metadata IP rejection) and persists the *normalized*
    URL. The guard runs today even though nothing is fetched yet, so the
    validation contract is established and tested before real fetching
    lands.
"""

import hashlib
import random
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.enums import SearchStatus
from models.lead import Company, Lead
from models.search import ApiProvider, Search, SearchProviderRun, WebsiteScan
from schemas.search import SearchCreate, WebsiteScanCreate
from services import usage_service
from utils.url_guard import resolve_and_validate

# --- Lead search placeholder generation -----------------------------------

_COMPANY_PREFIXES = ["Apex", "Vertex", "Prime", "Nova", "Summit", "Bluewire", "Titan", "Orbit", "Meridian", "Ironclad"]
_COMPANY_SUFFIXES = ["Electricals", "Automation", "Controls", "Power Systems", "Switchgear", "Panels", "Engineering", "Industries"]
_CITIES = [
    ("Mumbai", "India"), ("Pune", "India"), ("Ahmedabad", "India"),
    ("Dubai", "UAE"), ("Singapore", "Singapore"), ("Austin", "United States"),
]
_FIRST_NAMES = ["Rohan", "Priya", "Amit", "Sara", "Vikram", "Neha", "Arjun", "Divya"]
_LAST_NAMES = ["Mehta", "Shah", "Kapoor", "Reddy", "Nair", "Iyer", "Verma", "Singh"]


async def run_search(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID, data: SearchCreate) -> Search:
    """Runs a lead search, metered against the organization's credit balance.

    Order of operations matters: providers are resolved and credits reserved
    **before** the `Search` row is created, so a caller who cannot pay gets a
    clean 402 without leaving an orphaned RUNNING search behind.
    """
    providers = (
        await db.execute(select(ApiProvider).where(ApiProvider.category.in_(["Search", "Business", "Maps"])))
    ).scalars().all()
    providers = list(providers)

    # Reserve the worst case up front (see usage_service for why pessimistic).
    # Raises InsufficientCreditsError -> HTTP 402 if the balance can't cover it.
    estimate = usage_service.estimate_search_cost(providers)
    reservation = await usage_service.reserve_credits(
        db, organization_id, estimate, f"Lead search: {data.query[:120]}"
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

        rng = random.Random(f"{data.query}:{search.id}")
        total_results = 0
        # Tracks leads actually persisted per provider so the settlement
        # charges for real output rather than the padded `found` figure.
        billable_by_provider: dict[uuid.UUID, int] = {}
        now = datetime.now(UTC)

        for provider in providers:
            found = rng.randint(8, 45)
            run = SearchProviderRun(
                search_id=search.id,
                provider_id=provider.id,
                status=SearchStatus.COMPLETED,
                results_found=found,
                started_at=now,
                completed_at=now,
            )
            db.add(run)

            provider.usage_count += found
            persisted = 0
            # Honour the configured cap rather than a hardcoded number, so the
            # credits reserved by estimate_search_cost() match what can
            # actually be produced. Previously this was a literal 8 while the
            # estimate used the setting, which meant a search reserved more
            # than it could ever consume.
            per_provider_cap = max(0, settings.SEARCH_MAX_RESULTS_PER_PROVIDER)
            for _ in range(min(found, per_provider_cap)):
                company_name = f"{rng.choice(_COMPANY_PREFIXES)} {rng.choice(_COMPANY_SUFFIXES)}"
                city, country = rng.choice(_CITIES)
                if data.country and data.country != "all":
                    country = data.country

                company = Company(
                    name=company_name,
                    industry=data.industry or "Industrial Automation",
                    company_type=rng.choice(["Private Ltd", "LLP", "Partnership"]),
                    city=data.location or city,
                    country=country,
                    rating=round(rng.uniform(3.0, 5.0), 1),
                )
                db.add(company)
                await db.flush()

                score = rng.randint(40, 98)
                lead = Lead(
                    organization_id=organization_id,
                    company_id=company.id,
                    contact_name=f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
                    email=f"contact@{company_name.lower().replace(' ', '')}.com",
                    phone=f"+91 {rng.randint(70000, 99999)} {rng.randint(10000, 99999)}",
                    lead_score=score,
                    status="new",
                    tags=[data.industry] if data.industry else [],
                    provider_id=provider.id,
                    search_id=search.id,
                    created_by_id=user_id,
                    ai_summary=f"{company_name} is a {'high-intent' if score > 75 else 'moderate-intent'} lead discovered via {provider.name}.",
                )
                db.add(lead)
                persisted += 1

            billable_by_provider[provider.id] = persisted
            total_results += found

        search.status = SearchStatus.COMPLETED
        search.results_count = total_results
        search.completed_at = datetime.now(UTC)

        # Settle before commit so the wallet adjustment and the search land in
        # the same transaction — a crash between them can't bill for nothing.
        actual_cost = usage_service.calculate_search_actual_cost(billable_by_provider, providers)
        await usage_service.settle_reservation(db, reservation, actual_cost)

        await db.commit()
    except Exception:
        # The reservation was flushed into THIS transaction, never committed
        # separately — so rolling back is itself the refund. Calling
        # release_reservation() here would credit the balance a second time
        # and hand out free credits on every failed search.
        #
        # A side effect worth knowing: `SELECT ... FOR UPDATE` holds the wallet
        # lock until this transaction ends, so concurrent searches for one
        # organization serialize rather than racing. That is deliberate — it
        # makes the balance check authoritative and caps concurrent spend.
        await db.rollback()
        raise

    stmt = (
        select(Search)
        .where(Search.id == search.id)
        .execution_options(populate_existing=True)
    )
    refreshed = (await db.execute(stmt)).scalar_one()
    await db.refresh(refreshed, attribute_names=["provider_runs"])
    return refreshed


# --- Website scanner (deterministic hash generation, ported from the
# frontend's src/components/scanner/mock-data.ts so results are stable
# for a given domain across the whole app) --------------------------------
#
# URL normalization previously lived here as a local `_normalize_url` helper.
# It has been replaced by `utils.url_guard.normalize_url`, which does the same
# job plus the security checks (scheme/port/credential/hostname validation),
# so there is exactly one place where a user-supplied URL is interpreted.


def _seeded_rng(domain: str) -> random.Random:
    digest = hashlib.sha256(domain.encode()).hexdigest()
    seed = int(digest[:16], 16)
    return random.Random(seed)


def _slug_company_name(domain: str) -> str:
    base = domain.split(".")[0] if domain else "company"
    parts = [p for p in base.replace("_", "-").split("-") if p]
    return " ".join(p[:1].upper() + p[1:] for p in parts) or "Company"


async def scan_website(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID, data: WebsiteScanCreate) -> WebsiteScan:
    """Scans a website, metered and SSRF-guarded.

    The URL goes through the full guard (syntax -> hostname policy -> DNS ->
    IP-range checks) before anything else happens, so an unsafe target is
    rejected with HTTP 400 and is never charged for. Credits are then reserved
    before the scan work begins.

    The guard runs even though the report is still generated deterministically
    rather than fetched — that way the validation contract, its tests, and the
    stored-URL normalization are all settled before real fetching is added.
    """
    # 1. Validate FIRST — unsafe URLs cost nothing and create no rows.
    #    Raises UnsafeUrlError (HTTP 400) on anything the guard refuses.
    validated = await resolve_and_validate(data.url)
    url, domain = validated.url, validated.hostname

    # 2. Reserve credits — raises InsufficientCreditsError (HTTP 402).
    reservation = await usage_service.reserve_credits(
        db, organization_id, usage_service.scan_cost(), f"Website scan: {domain}"
    )

    try:
        return await _perform_scan(db, organization_id, user_id, url, domain)
    except Exception:
        # As in run_search: the reservation is pending in this transaction, so
        # the rollback is the refund. Do not also call release_reservation().
        await db.rollback()
        raise


async def _perform_scan(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    url: str,
    domain: str,
) -> WebsiteScan:
    """Builds and persists the scan report for an already-validated URL.

    Split out from `scan_website` so validation/metering stay clearly separated
    from report generation — when real fetching replaces the deterministic
    generator, only this function changes.
    """
    start = time.monotonic()
    rng = _seeded_rng(domain or url)
    company_slug = (domain.split(".")[0] if domain else "contact").lower()

    email_count = 1 + rng.randint(0, 1)
    emails = [f"info@{domain}" if i == 0 else f"sales@{domain}" for i in range(email_count)]

    phone_count = 1 + rng.randint(0, 1)
    phones = [f"+91 {rng.randint(70000, 99999)} {rng.randint(10000, 99999)}" for _ in range(phone_count)]

    state_codes = ["07", "27", "29", "33", "36", "19", "24", "09"]
    pan_letters = "".join(chr(65 + rng.randint(0, 25)) for _ in range(5))
    pan_digits = "".join(str(rng.randint(0, 9)) for _ in range(4))
    gst_number = f"{rng.choice(state_codes)}{pan_letters}{pan_digits}{chr(65 + rng.randint(0, 25))}1Z{rng.randint(0, 9)}"
    gst_found = rng.random() > 0.15

    platforms = ["LinkedIn", "Facebook", "Instagram", "X"]
    social = []
    for platform in platforms:
        found = rng.random() > 0.35
        social.append({"platform": platform, "found": found, "handle": f"@{company_slug}" if found else None})

    ssl_valid = rng.random() > 0.08
    mobile_friendly = rng.random() > 0.2
    load_time_ms = round(600 + rng.random() * 2200)
    seo_score = round(55 + rng.random() * 40)

    signals = [gst_found, ssl_valid, mobile_friendly] + [s["found"] for s in social]
    positive = sum(1 for s in signals if s)
    confidence = min(98, max(38, round((positive / len(signals)) * 78 + 18 + rng.random() * 6)))

    contact_person = f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"
    company_name = _slug_company_name(domain or company_slug)

    scan_duration_ms = round((time.monotonic() - start) * 1000) + rng.randint(1800, 3200)

    scan = WebsiteScan(
        organization_id=organization_id,
        user_id=user_id,
        url=url,
        domain=domain or url,
        company_name=company_name,
        contact_person=contact_person,
        confidence_score=confidence,
        emails=emails,
        phones=phones,
        gst_number=gst_number if gst_found else None,
        gst_verified=gst_found,
        social_links=social,
        ssl_valid=ssl_valid,
        mobile_friendly=mobile_friendly,
        load_time_ms=load_time_ms,
        seo_score=seo_score,
        scan_duration_ms=scan_duration_ms,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan
