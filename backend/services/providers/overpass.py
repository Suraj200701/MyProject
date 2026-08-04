"""Overpass API provider: OSM POI search by keyword, place and radius.

    POST {OVERPASS_URL}    body: data=<Overpass QL>

No API key. Overpass is donated infrastructure and defends itself accordingly —
measured while building this, it returned **429 on 8 of 12** requests spaced 1.2s
apart, and **504** on a heavier one, with **HTML error bodies**. Three consequences
shape this module:

1. **One request per search.** Every keyword and every element type is unioned
   into a single query. Issuing one request per tag is what triggered the 429s.
2. **Retry with backoff.** `providers.http.request_json` already treats 429 and
   5xx as transient and retries with exponential backoff; a generous timeout is
   passed because Overpass is legitimately slow.
3. **Failures degrade, never propagate.** A throttled or timed-out Overpass
   returns a FAILED `ProviderSearchResult`, so the rest of the search completes.

Turning a keyword into a query
------------------------------
Two strategies, unioned, because neither alone is sufficient:

* **Tag selectors** for concepts OSM models directly — `amenity=restaurant`,
  `amenity=hospital`, `man_made=works`. Precise, and finds businesses whose name
  says nothing about what they do.
* **Case-insensitive name regex** for concepts OSM has no tag for. "PLC",
  "SCADA", "Panel Builder" and "Industrial Automation" are not OSM tags and never
  will be; the only way to find them is `["name"~"...",i]`.

A keyword with no tag mapping still searches by name, so nothing is silently
unsupported.

Geometry
--------
Overpass needs a spatial filter, so a location is geocoded through Nominatim
first and becomes `(around:<radius_m>,<lat>,<lon>)`. Note the argument order is
radius, latitude, longitude — unlike the lon-first GeoJSON convention used by
other providers in this codebase.

`out center tags` is required: ways and relations carry no `lat`/`lon`, only a
`center` when asked for it, and most industrial premises are ways.
"""

from __future__ import annotations

import logging
import re

from config.settings import settings
from services.providers.base import (
    NormalizedLead,
    ProviderRunStatus,
    ProviderSearchResult,
    SearchQuery,
    failed,
    skipped,
)
from services.providers.http import (
    PermanentProviderError,
    TransientProviderError,
    request_json,
)
from services.providers.openstreetmap import NominatimClient
from services.providers.osm_common import (
    element_coordinates,
    extract_osm_fields,
    overpass_cache,
)

logger = logging.getLogger("leadmaster.providers.overpass")

# Radius bounds from the integration spec. Overpass will happily accept a
# 500km circle and then time out, so the ceiling is a courtesy as much as a
# constraint.
MIN_RADIUS_KM = 1
MAX_RADIUS_KM = 100
DEFAULT_RADIUS_KM = 25

# Overpass is slow by design — it is running a database query, not serving a
# cached index. Its own `[timeout:]` is set just below this.
# Measured against the public instance: an accepted query answers in ~10-35s.
# The server-side `[timeout:]` is kept low so Overpass gives up and replies
# instead of leaving the client hanging, and the client timeout sits just above
# it. 90s here made a whole multi-provider search wait on one slow provider.
REQUEST_TIMEOUT_SECONDS = 45.0
QUERY_TIMEOUT_SECONDS = 25

# Element types searched. Relations are included because industrial estates and
# hospital campuses are frequently mapped as relations.
_ELEMENT_TYPES = ("node", "way", "relation")

# Keyword -> OSM tag selectors, from the documented OSM tag vocabulary.
# Selectors are raw Overpass QL fragments, appended directly after the element
# type. Only concepts OSM actually models appear here; everything else falls
# through to the name regex.
_KEYWORD_SELECTORS: dict[str, tuple[str, ...]] = {
    # Hospitality / retail
    "restaurant": ('["amenity"="restaurant"]',),
    "cafe": ('["amenity"="cafe"]',),
    "bar": ('["amenity"="bar"]', '["amenity"="pub"]'),
    "hotel": ('["tourism"="hotel"]',),
    "supermarket": ('["shop"="supermarket"]',),
    "shop": ('["shop"]',),
    "store": ('["shop"]',),
    "retail": ('["shop"]',),
    "wholesale": ('["shop"="wholesale"]',),
    "distributor": ('["shop"="wholesale"]', '["office"="company"]'),
    "dealer": ('["shop"="car"]', '["shop"="trade"]'),
    "car dealer": ('["shop"="car"]',),
    # Healthcare
    "hospital": ('["amenity"="hospital"]',),
    "clinic": ('["amenity"="clinic"]', '["healthcare"="clinic"]'),
    "doctor": ('["amenity"="doctors"]',),
    "dentist": ('["amenity"="dentist"]',),
    "pharmacy": ('["amenity"="pharmacy"]',),
    "laboratory": ('["healthcare"="laboratory"]',),
    # Industry / manufacturing
    "factory": ('["man_made"="works"]', '["building"="industrial"]', '["landuse"="industrial"]'),
    "manufacturer": ('["man_made"="works"]', '["industrial"]'),
    "manufacturing": ('["man_made"="works"]', '["industrial"]'),
    "industrial": ('["industrial"]', '["landuse"="industrial"]', '["building"="industrial"]'),
    "warehouse": ('["building"="warehouse"]', '["landuse"="industrial"]'),
    "workshop": ('["craft"]',),
    "foundry": ('["industrial"="foundry"]',),
    # Energy
    "solar": ('["generator:source"="solar"]', '["plant:source"="solar"]'),
    "wind": ('["generator:source"="wind"]', '["plant:source"="wind"]'),
    "power": ('["power"]',),
    "ev": ('["amenity"="charging_station"]',),
    "ev charging": ('["amenity"="charging_station"]',),
    "charging station": ('["amenity"="charging_station"]',),
    # Trades / services
    "electrical": ('["craft"="electrician"]', '["shop"="electrical"]', '["office"="company"]'),
    "electrician": ('["craft"="electrician"]',),
    "engineering": ('["office"="engineer"]', '["craft"]'),
    "office": ('["office"]',),
    "company": ('["office"="company"]',),
    "business": ('["office"]', '["shop"]'),
    "logistics": ('["office"="logistics"]', '["building"="warehouse"]'),
    "construction": ('["craft"="builder"]', '["office"="construction_company"]'),
    # Education
    "school": ('["amenity"="school"]',),
    "college": ('["amenity"="college"]',),
    "university": ('["amenity"="university"]',),
}

# Longest first so "car dealer" wins over "dealer", "ev charging" over "ev".
_KEYWORDS_BY_LENGTH = tuple(sorted(_KEYWORD_SELECTORS, key=len, reverse=True))

# Keywords too generic to be worth a name regex — matching every element whose
# name contains "office" would return noise, not leads.
_NO_NAME_REGEX = {"shop", "store", "retail", "office", "business", "company", "power"}

# Overpass regex is used inside a double-quoted string, so a literal `"` or `\`
# would terminate or escape it. Regex metacharacters are escaped too: a keyword
# is a search term, not a pattern the user is writing.
_UNSAFE_REGEX = re.compile(r'[\\"]')


def clamp_radius_km(radius_km: float | None) -> int:
    """Radius in kilometres, clamped to the supported 1-100km band."""
    if radius_km is None:
        return DEFAULT_RADIUS_KM
    try:
        value = float(radius_km)
    except (TypeError, ValueError):
        return DEFAULT_RADIUS_KM
    return int(max(MIN_RADIUS_KM, min(MAX_RADIUS_KM, value)))


def split_keywords(text: str) -> list[str]:
    """Splits a multi-keyword query into individual terms.

    Users type "solar, wind, EV" or "solar and wind" or "solar | wind". Anything
    that is clearly a separator becomes one, and the whole phrase is kept as a
    term too so "industrial automation" still matches as a phrase.
    """
    if not text:
        return []

    phrase = " ".join(text.split())
    parts = [p.strip() for p in re.split(r"[,;|/]|\band\b|\+", phrase, flags=re.I)]
    terms = [p for p in parts if p]

    # Preserve the full phrase first (most specific), then the parts.
    ordered: list[str] = []
    for candidate in [phrase, *terms]:
        lowered = candidate.lower()
        if lowered and lowered not in {o.lower() for o in ordered}:
            ordered.append(candidate)
    return ordered


def selectors_for(keyword: str) -> tuple[str, ...]:
    """Tag selectors implied by one keyword. Empty when OSM has no tag for it."""
    haystack = " ".join(keyword.lower().replace("-", " ").replace("_", " ").split())
    padded = f" {haystack} "
    for candidate in _KEYWORDS_BY_LENGTH:
        if f" {candidate} " in padded:
            return _KEYWORD_SELECTORS[candidate]
    return ()


def _escape_regex_literal(keyword: str) -> str:
    """A keyword made safe to embed in an Overpass double-quoted regex."""
    return _UNSAFE_REGEX.sub("", keyword).replace("(", r"\\(").replace(")", r"\\)")


def build_query(
    keywords: list[str], lat: float, lng: float, radius_km: int, limit: int
) -> str:
    """Overpass QL for these keywords within `radius_km` of a point.

    One statement per (element type x selector) plus one per (element type x name
    regex), all unioned into a single request — see the module docstring for why
    that matters.
    """
    radius_m = radius_km * 1000
    # `around` takes radius, lat, lon — NOT the lon-first order used elsewhere.
    around = f"(around:{radius_m},{lat},{lng})"

    statements: list[str] = []
    seen: set[str] = set()

    def add(fragment: str) -> None:
        for element in _ELEMENT_TYPES:
            statement = f"  {element}{fragment}{around};"
            if statement not in seen:
                seen.add(statement)
                statements.append(statement)

    for keyword in keywords:
        selectors = selectors_for(keyword)
        if selectors:
            # Tags win, and the name regex is deliberately NOT added alongside
            # them. Measured against the public instance: a tag-only query for
            # "hospital" answered in ~19s, while tag+regex was throttled with a
            # 429 and returned nothing. Precision that completes beats extra
            # recall that gets rejected — and a keyword with tags is exactly the
            # case where tags are the reliable signal.
            for selector in selectors:
                add(selector)
            continue

        lowered = keyword.lower()
        if lowered not in _NO_NAME_REGEX and len(lowered) >= 2:
            escaped = _escape_regex_literal(keyword)
            if escaped:
                # The only way to find concepts OSM has no tag for — "PLC",
                # "SCADA", "Panel Builder", "Industrial Automation".
                add(f'["name"~"{escaped}",i]')

    if not statements:
        # Defensive: `search()` refuses an empty keyword before reaching here.
        raise ValueError("no Overpass statements could be built for these keywords")

    body = "\n".join(statements)
    return (
        f"[out:json][timeout:{QUERY_TIMEOUT_SECONDS}];\n"
        f"(\n{body}\n);\n"
        # `center` supplies coordinates for ways/relations, which have none of
        # their own; `tags` returns the fields we extract from.
        f"out center tags {limit};"
    )


class OverpassProvider:
    """Sources leads from the Overpass API."""

    name = "Overpass API"

    def __init__(self, overpass_url: str | None = None) -> None:
        self._url = overpass_url or settings.OVERPASS_URL
        self._geocoder = NominatimClient()

    @property
    def is_configured(self) -> bool:
        """No API key exists for Overpass; only an endpoint is needed."""
        return bool(self._url)

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        if not self.is_configured:
            return skipped(self.name, "OVERPASS_URL is not configured")

        keywords = split_keywords(query.query)
        if query.industry:
            keywords.extend(k for k in split_keywords(query.industry) if k not in keywords)
        if not keywords:
            return skipped(self.name, "A keyword is required to build an Overpass query.")

        location_text = (query.location or "").strip()
        if not location_text:
            return skipped(
                self.name,
                "Overpass searches a radius around a place, so a location is required "
                "(e.g. 'panel builders in Pune').",
            )

        try:
            centre = await self._geocoder.geocode(location_text)
        except (PermanentProviderError, TransientProviderError) as exc:
            # Geocoding is a separate service; say which step failed.
            return failed(self.name, f"Could not geocode {location_text!r}: {exc}")

        if centre is None:
            return failed(self.name, f"OpenStreetMap could not locate {location_text!r}")

        radius_km = clamp_radius_km(query.radius_km)
        try:
            ql = build_query(keywords, centre["lat"], centre["lng"], radius_km, query.max_results)
        except ValueError as exc:
            return skipped(self.name, str(exc))

        cached = overpass_cache.get(ql)
        if cached is not None:
            elements = cached
            logger.info("Overpass cache hit for %s keyword(s) near %s", len(keywords), location_text)
        else:
            try:
                payload, latency_ms = await request_json(
                    "POST",
                    self._url,
                    # The documented POST form. Overpass also accepts a raw body,
                    # but `data=` is what its docs specify.
                    form_body={"data": ql},
                    headers={"User-Agent": settings.OSM_USER_AGENT},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except PermanentProviderError as exc:
                # Overpass error bodies are HTML; `request_json` already truncates.
                logger.warning("Overpass rejected the query: %s", exc)
                return failed(self.name, str(exc))
            except TransientProviderError as exc:
                # Throttled or overloaded after retries. The search continues with
                # whatever the other providers found.
                logger.warning("Overpass unavailable after retries: %s", exc)
                return failed(self.name, f"Temporarily unavailable (throttled or busy): {exc}")

            elements = payload.get("elements") or []
            overpass_cache.put(ql, elements)
            logger.info(
                "Overpass returned %s element(s) for %s within %skm of %s (%sms)",
                len(elements),
                ", ".join(keywords[:4]),
                radius_km,
                centre["formatted_address"],
                latency_ms,
            )

        leads = [
            lead for element in elements if (lead := self._to_lead(element, query)) is not None
        ]
        return ProviderSearchResult(
            provider_name=self.name,
            status=ProviderRunStatus.COMPLETED,
            leads=leads[: query.max_results],
        )

    def _to_lead(self, element: dict, query: SearchQuery) -> NormalizedLead | None:
        tags = element.get("tags") or {}
        fields = extract_osm_fields(tags)

        name = fields["name"]
        if not name:
            # An unnamed way (a building outline, a plot of industrial land) is
            # geography, not a business.
            return None

        lat, lng = element_coordinates(element)
        osm_type, osm_id = element.get("type"), element.get("id")

        return NormalizedLead(
            company_name=name,
            industry=query.industry or fields["category"],
            website=fields["website"],
            address=fields["address"],
            # OSM elements often carry no addr:city; fall back to the searched
            # place so the lead stays filterable and dedupable by city.
            city=fields["city"] or fields["district"] or query.location,
            country=fields["country"] or query.country,
            lat=lat,
            lng=lng,
            email=fields["email"],
            phone=fields["phone"] or fields["mobile"],
            tags=[t for t in [query.industry] if t],
            raw={
                "source": "Overpass API (OpenStreetMap)",
                "osm_type": osm_type,
                "osm_id": osm_id,
                "osm_element": f"{osm_type}/{osm_id}" if osm_type and osm_id else None,
                "category": fields["category"],
                "subcategory": fields["subcategory"],
                "street": fields["street"],
                "housenumber": fields["housenumber"],
                "area": fields["area"],
                "district": fields["district"],
                "state": fields["state"],
                "postal_code": fields["postal_code"],
                "mobile": fields["mobile"],
                "opening_hours": fields["opening_hours"],
                "operator": fields["operator"],
                "brand": fields["brand"],
                "wheelchair": fields["wheelchair"],
                "payment_methods": fields["payment_methods"] or None,
                "social": fields["social"] or None,
            },
            source_provider=self.name,
        )
