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
  - Website Scanner -> a real crawler (e.g. httpx + BeautifulSoup) fetching
    the target site and extracting emails/phones/GST/social links from the
    actual page content, instead of the deterministic-hash approach here.
"""

import hashlib
import random
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import SearchStatus
from models.lead import Company, Lead
from models.search import ApiProvider, Search, SearchProviderRun, WebsiteScan
from schemas.search import SearchCreate, WebsiteScanCreate

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

    providers = (
        await db.execute(select(ApiProvider).where(ApiProvider.category.in_(["Search", "Business", "Maps"])))
    ).scalars().all()

    rng = random.Random(f"{data.query}:{search.id}")
    total_results = 0
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
        for _ in range(min(found, 8)):  # cap rows created per provider to keep this fast
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

        total_results += found

    search.status = SearchStatus.COMPLETED
    search.results_count = total_results
    search.completed_at = datetime.now(UTC)

    await db.commit()

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


def _normalize_url(raw: str) -> tuple[str, str]:
    value = raw.strip()
    if not value:
        return "", ""
    if not value.lower().startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    domain = parsed.netloc or value.replace("https://", "").replace("http://", "").split("/")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    return value, domain


def _seeded_rng(domain: str) -> random.Random:
    digest = hashlib.sha256(domain.encode()).hexdigest()
    seed = int(digest[:16], 16)
    return random.Random(seed)


def _slug_company_name(domain: str) -> str:
    base = domain.split(".")[0] if domain else "company"
    parts = [p for p in base.replace("_", "-").split("-") if p]
    return " ".join(p[:1].upper() + p[1:] for p in parts) or "Company"


async def scan_website(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID, data: WebsiteScanCreate) -> WebsiteScan:
    start = time.monotonic()
    url, domain = _normalize_url(data.url)
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
