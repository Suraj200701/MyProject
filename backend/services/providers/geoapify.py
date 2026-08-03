"""Geoapify adapter: OpenStreetMap-derived places, geocoding and autocomplete.

Why this provider matters here
-----------------------------
It is the only configured source that returns **coordinates**. Google Places
needs a key this deployment does not have, and the Mappls project is not licensed
for coordinate delivery (its Places responses omit lat/lng and its geocoding
endpoints answer 412). Geoapify supplies both, which is what makes map plotting
and radius work possible at all.

Two version prefixes
--------------------
Places lives under `/v2`, geocoding under `/v1` — `/v2/geocode/search` returns
404 "not supported". `settings.geoapify_origin` strips whichever version a
configured base URL carries so each endpoint can append its own.

Keyword -> category, and why a search is two requests
-----------------------------------------------------
The Places API **requires** `categories` (or `type`); a free-text `name` alone is
rejected with 400. It also requires a spatial filter. So "dentists in Ahmedabad"
becomes:

    1. GET /v1/geocode/search?text=Ahmedabad          -> lon/lat
    2. GET /v2/places?categories=healthcare.dentist
           &filter=circle:<lon>,<lat>,<radius>        -> businesses

`_KEYWORD_CATEGORIES` maps everyday search words onto Geoapify's fixed taxonomy.
Every code in it was verified against the live API — Geoapify rejects unknown
codes with a 400, and several plausible-looking ones (`healthcare.clinic`,
`commercial.electronics`, `service.vehicle.car_repair`) do not exist. An
unmapped keyword is *skipped with an explanation* rather than sent as a broad
`commercial` sweep, because returning unrelated businesses is worse than
returning none.

Data quality
------------
Coordinates and addresses are near-universal. `website`/`phone` come from
OpenStreetMap tagging and were present on roughly 1 in 5 sampled features — real
but sparse, which is why the import/enrichment path (visit the site, extract
contacts) still earns its place.
"""

from __future__ import annotations

import logging

from config.settings import settings
from services.enrichment.address import parse_address
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

logger = logging.getLogger("leadmaster.providers.geoapify")

# Geoapify caps `limit` at 500 for Places.
MAX_PLACES_LIMIT = 500

# Everyday search words -> Geoapify category codes.
#
# Only codes that returned HTTP 200 from the live API are listed. Keys are
# matched as whole words against the lowercased query, longest first, so
# "dental clinic" beats "clinic".
_KEYWORD_CATEGORIES: dict[str, tuple[str, ...]] = {
    # Food & drink
    "restaurant": ("catering.restaurant",),
    "restaurants": ("catering.restaurant",),
    "cafe": ("catering.cafe",),
    "cafes": ("catering.cafe",),
    "coffee": ("catering.cafe",),
    "bar": ("catering.bar", "catering.pub"),
    "bars": ("catering.bar", "catering.pub"),
    "pub": ("catering.pub",),
    "fast food": ("catering.fast_food",),
    "takeaway": ("catering.fast_food",),
    "bakery": ("commercial.food_and_drink.bakery",),
    "bakeries": ("commercial.food_and_drink.bakery",),
    # Accommodation
    "hotel": ("accommodation.hotel",),
    "hotels": ("accommodation.hotel",),
    "guest house": ("accommodation.guest_house",),
    "guesthouse": ("accommodation.guest_house",),
    # Healthcare
    "dentist": ("healthcare.dentist",),
    "dentists": ("healthcare.dentist",),
    "dental": ("healthcare.dentist",),
    "dental clinic": ("healthcare.dentist",),
    "clinic": ("healthcare.clinic_or_praxis",),
    "clinics": ("healthcare.clinic_or_praxis",),
    "doctor": ("healthcare.clinic_or_praxis",),
    "doctors": ("healthcare.clinic_or_praxis",),
    "hospital": ("healthcare.hospital",),
    "hospitals": ("healthcare.hospital",),
    "pharmacy": ("healthcare.pharmacy",),
    "pharmacies": ("healthcare.pharmacy",),
    "chemist": ("healthcare.pharmacy",),
    # Wellness
    "gym": ("sport.fitness",),
    "gyms": ("sport.fitness",),
    "fitness": ("sport.fitness",),
    "spa": ("leisure.spa",),
    "salon": ("service.beauty", "service.beauty.hairdresser"),
    "salons": ("service.beauty", "service.beauty.hairdresser"),
    "beauty": ("service.beauty",),
    "hairdresser": ("service.beauty.hairdresser",),
    "barber": ("service.beauty.hairdresser",),
    # Professional services
    "lawyer": ("office.lawyer",),
    "lawyers": ("office.lawyer",),
    "legal": ("office.lawyer",),
    "advocate": ("office.lawyer",),
    "estate agent": ("office.estate_agent",),
    "real estate": ("office.estate_agent",),
    "property": ("office.estate_agent",),
    "insurance": ("office.insurance",),
    "bank": ("service.financial.bank",),
    "banks": ("service.financial.bank",),
    "office": ("office.company",),
    "offices": ("office.company",),
    "company": ("office.company",),
    "companies": ("office.company",),
    "business": ("office.company", "commercial"),
    "businesses": ("office.company", "commercial"),
    "travel agent": ("service.travel_agency",),
    "travel agency": ("service.travel_agency",),
    "cleaning": ("service.cleaning",),
    "taxi": ("service.taxi",),
    # Education
    "school": ("education.school",),
    "schools": ("education.school",),
    "college": ("education.college",),
    "colleges": ("education.college",),
    "university": ("education.university",),
    "universities": ("education.university",),
    # Retail & trade
    "supermarket": ("commercial.supermarket",),
    "supermarkets": ("commercial.supermarket",),
    "grocery": ("commercial.supermarket",),
    "clothing": ("commercial.clothing",),
    "clothes": ("commercial.clothing",),
    "shop": ("commercial",),
    "shops": ("commercial",),
    "store": ("commercial",),
    "stores": ("commercial",),
    "retail": ("commercial",),
    "market": ("commercial.marketplace",),
    "car dealer": ("commercial.vehicle",),
    "car dealers": ("commercial.vehicle",),
    "garage": ("service.vehicle",),
    "car service": ("service.vehicle",),
    "manufacturer": ("production",),
    "manufacturers": ("production",),
    "manufacturing": ("production",),
    "factory": ("production",),
    "factories": ("production",),
}

# Longest keywords first so multi-word phrases win over their constituent words.
_KEYWORDS_BY_LENGTH = tuple(sorted(_KEYWORD_CATEGORIES, key=len, reverse=True))

# A representative sample for the "unsupported keyword" message. The full map is
# large; naming a handful is more useful than dumping all of it.
_EXAMPLE_KEYWORDS = (
    "restaurants, cafes, hotels, dentists, clinics, hospitals, pharmacies, gyms, "
    "salons, lawyers, real estate, insurance, banks, schools, supermarkets, "
    "car dealers, manufacturers"
)


def categories_for(query: str, industry: str | None = None) -> tuple[str, ...]:
    """Geoapify category codes implied by a free-text query.

    Matched as whole words so "barbecue" does not match "bar". Returns an empty
    tuple when nothing is recognised, which the caller reports as skipped.
    """
    haystack = f"{query or ''} {industry or ''}".lower()
    # Normalize separators to spaces so "car-dealer" and "car_dealer" match.
    for char in "-_/,.":
        haystack = haystack.replace(char, " ")
    padded = f" {' '.join(haystack.split())} "

    for keyword in _KEYWORDS_BY_LENGTH:
        if f" {keyword} " in padded:
            return _KEYWORD_CATEGORIES[keyword]
    return ()


class GeoapifyClient:
    """Authenticated access to the Geoapify REST APIs.

    Separate from the provider so `services/maps_service.py` can use the
    geocoding endpoints without the lead-search machinery.
    """

    def __init__(self, api_key: str | None = None):
        # Read at call time so tests that patch settings take effect.
        self.api_key = api_key or settings.GEOAPIFY_API_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _url(self, version: str, path: str) -> str:
        return f"{settings.geoapify_origin}/{version}/{path.lstrip('/')}"

    async def _get(self, version: str, path: str, params: dict) -> tuple[dict, int]:
        return await request_json(
            "GET", self._url(version, path), params={**params, "apiKey": self.api_key}
        )

    # --- Geocoding (v1) -------------------------------------------------

    async def geocode(self, text: str) -> dict | None:
        """Resolves free text to coordinates. Returns None when nothing matched."""
        payload, _ = await self._get("v1", "geocode/search", {"text": text, "limit": 1})
        features = payload.get("features") or []
        if not features:
            return None

        properties = features[0].get("properties") or {}
        lat, lon = _as_float(properties.get("lat")), _as_float(properties.get("lon"))
        if lat is None or lon is None:
            return None
        return {
            "lat": lat,
            "lng": lon,
            "formatted_address": properties.get("formatted") or text,
        }

    async def reverse_geocode(self, lat: float, lng: float) -> dict | None:
        payload, _ = await self._get("v1", "geocode/reverse", {"lat": lat, "lon": lng})
        features = payload.get("features") or []
        if not features:
            return None

        properties = features[0].get("properties") or {}
        return {
            "lat": _as_float(properties.get("lat")) or lat,
            "lng": _as_float(properties.get("lon")) or lng,
            "formatted_address": properties.get("formatted") or "",
        }

    async def autocomplete(self, text: str, limit: int = 5) -> list[dict]:
        payload, _ = await self._get("v1", "geocode/autocomplete", {"text": text, "limit": limit})
        return [
            {
                "name": (f.get("properties") or {}).get("address_line1"),
                "address": (f.get("properties") or {}).get("formatted"),
                "lat": _as_float((f.get("properties") or {}).get("lat")),
                "lng": _as_float((f.get("properties") or {}).get("lon")),
                "type": (f.get("properties") or {}).get("result_type"),
            }
            for f in (payload.get("features") or [])
        ]

    # --- Places (v2) ----------------------------------------------------

    async def places_in_circle(
        self, categories: tuple[str, ...], lat: float, lng: float, radius_m: int, limit: int
    ) -> list[dict]:
        """POIs of the given categories within a circle. Returns GeoJSON features."""
        payload, _ = await self._get(
            "v2",
            "places",
            {
                "categories": ",".join(categories),
                # circle is `lon,lat,radius` — longitude FIRST, GeoJSON order.
                # Swapping them silently searches the wrong hemisphere.
                "filter": f"circle:{lng},{lat},{radius_m}",
                "limit": max(1, min(limit, MAX_PLACES_LIMIT)),
            },
        )
        return payload.get("features") or []


class GeoapifyProvider:
    """Sources business leads from Geoapify Places."""

    name = "Geoapify"

    def __init__(self, api_key: str | None = None):
        self._client = GeoapifyClient(api_key)

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        if not self.is_configured:
            return skipped(self.name, "GEOAPIFY_API_KEY is not configured")

        categories = categories_for(query.query, query.industry)
        if not categories:
            # Honest skip. A broad `commercial` fallback would return whatever
            # shops happen to be nearby, which reads as the search "working".
            return skipped(
                self.name,
                f"No Geoapify category matches {query.query!r}. Supported keywords include: "
                f"{_EXAMPLE_KEYWORDS}.",
            )

        location_text = (query.location or "").strip()
        if not location_text:
            return skipped(
                self.name,
                "Geoapify searches a radius around a place, so a location is required "
                "(e.g. 'dentists in Ahmedabad').",
            )

        try:
            centre = await self._client.geocode(location_text)
            if centre is None:
                return failed(self.name, f"Geoapify could not locate {location_text!r}")

            features = await self._client.places_in_circle(
                categories,
                centre["lat"],
                centre["lng"],
                settings.GEOAPIFY_SEARCH_RADIUS_METERS,
                query.max_results,
            )
        except PermanentProviderError as exc:
            logger.warning("Geoapify rejected the request: %s", exc)
            return failed(self.name, str(exc))
        except TransientProviderError as exc:
            logger.warning("Geoapify temporarily unavailable: %s", exc)
            return failed(self.name, f"Temporarily unavailable: {exc}")

        leads = [
            lead for feature in features if (lead := self._to_lead(feature, query)) is not None
        ]
        logger.info(
            "Geoapify returned %s place(s) for %s near %s (%s usable)",
            len(features),
            ",".join(categories),
            centre["formatted_address"],
            len(leads),
        )

        return ProviderSearchResult(
            provider_name=self.name,
            status=ProviderRunStatus.COMPLETED,
            leads=leads[: query.max_results],
            latency_ms=0,
        )

    def _to_lead(self, feature: dict, query: SearchQuery) -> NormalizedLead | None:
        properties = feature.get("properties") or {}
        name = properties.get("name") or properties.get("address_line1")
        if not name:
            # Unnamed POIs (a bare building footprint) are not leads.
            return None

        address = properties.get("formatted") or properties.get("address_line2")
        parsed = parse_address(address)

        # Geoapify's own administrative fields beat anything parsed from the
        # formatted string; `city` is often absent for suburban POIs, so fall
        # back through the hierarchy it does provide.
        city = (
            properties.get("city")
            or properties.get("state_district")
            or properties.get("suburb")
            or properties.get("county")
            or parsed.city
            or query.location
        )

        contact = properties.get("contact") or {}
        phone = properties.get("phone") or contact.get("phone") or contact.get("mobile")
        email = properties.get("email") or contact.get("email")

        return NormalizedLead(
            company_name=name,
            industry=query.industry or _primary_category(properties),
            website=properties.get("website"),
            address=address,
            city=city,
            country=properties.get("country") or query.country,
            lat=_as_float(properties.get("lat")),
            lng=_as_float(properties.get("lon")),
            email=email,
            phone=phone,
            tags=[t for t in [query.industry] if t],
            raw={
                "place_id": properties.get("place_id"),
                "categories": properties.get("categories"),
                "postcode": properties.get("postcode") or parsed.postal_code,
                "state": properties.get("state") or parsed.state,
                "street": properties.get("street"),
                "opening_hours": properties.get("opening_hours"),
                "datasource": (properties.get("datasource") or {}).get("sourcename"),
            },
            source_provider=self.name,
        )


def _primary_category(properties: dict) -> str | None:
    """The most specific Geoapify category, as a human-ish industry label.

    Categories arrive coarse-to-fine (`catering`, `catering.restaurant`), so the
    longest one is the most specific. `catering.restaurant` -> "Restaurant".
    """
    categories = properties.get("categories") or []
    if not categories:
        return None
    most_specific = max(categories, key=len)
    return most_specific.rsplit(".", 1)[-1].replace("_", " ").title()


def _as_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
