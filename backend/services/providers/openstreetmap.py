"""OpenStreetMap provider: Nominatim geocoding + place search.

Official public endpoints only, no API key:

    forward   GET https://nominatim.openstreetmap.org/search
    reverse   GET https://nominatim.openstreetmap.org/reverse
    tiles     https://tile.openstreetmap.org/{z}/{x}/{y}.png   (used by the client)

Usage policy, and why it is enforced here
-----------------------------------------
Nominatim is donated infrastructure with a published policy: an identifying
`User-Agent` is **required** (requests without one are rejected) and callers are
capped at **1 request per second**. Both are handled in this module —
`osm_common.nominatim_limiter` is process-wide, so a caller cannot accidentally
burst past the limit, and identical queries are served from a short-lived cache.

Nominatim is a *geocoder* first. Its `/search` endpoint does return POIs, which
makes a modest lead source, but its policy explicitly discourages bulk POI
harvesting — Overpass is the right tool for that, and this deployment has an
Overpass provider for exactly that reason. So the result limit here stays small
and the heavy lifting belongs to `overpass.py`.

Coordinates arrive as **strings** (`"23.0215374"`), which is why everything goes
through `_as_float` rather than being trusted as numeric.
"""

from __future__ import annotations

import logging

from config.settings import settings
from services.providers.base import (
    NormalizedLead,
    ProviderRunStatus,
    ProviderSearchResult,
    SearchQuery,
    failed,
)
from services.providers.http import (
    PermanentProviderError,
    TransientProviderError,
    request_json,
)
from services.providers.osm_common import (
    _as_float,
    extract_osm_fields,
    nominatim_cache,
    nominatim_limiter,
    osm_category,
)

logger = logging.getLogger("leadmaster.providers.osm")

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
SEARCH_URL = f"{NOMINATIM_BASE_URL}/search"
REVERSE_URL = f"{NOMINATIM_BASE_URL}/reverse"

# Nominatim's own hard ceiling is 40; staying well under it keeps a single user
# query from looking like harvesting.
MAX_SEARCH_RESULTS = 20

# Nominatim can be slow on cold cache entries; it is also being generous with
# free capacity, so give it room rather than retrying aggressively.
REQUEST_TIMEOUT_SECONDS = 20.0


def _headers() -> dict[str, str]:
    """Identifying User-Agent, which Nominatim requires."""
    return {"User-Agent": settings.OSM_USER_AGENT, "Accept": "application/json"}


class NominatimClient:
    """Geocoding against the public Nominatim instance.

    Separate from the provider so `services/maps_service.py` can use geocoding
    without the lead-search machinery — the same split as Mappls and Geoapify.
    """

    @property
    def is_configured(self) -> bool:
        """Always true: the service needs no credentials, only a User-Agent."""
        return bool(settings.OSM_USER_AGENT)

    async def _get(self, url: str, params: dict) -> list | dict:
        cache_key = f"{url}?{sorted(params.items())}"
        cached = nominatim_cache.get(cache_key)
        if cached is not None:
            return cached

        await nominatim_limiter.acquire()
        payload, _latency = await request_json(
            "GET",
            url,
            params={**params, "format": "jsonv2"},
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        nominatim_cache.put(cache_key, payload)
        return payload

    async def geocode(self, address: str) -> dict | None:
        """Forward geocode free text to coordinates. None when nothing matched."""
        results = await self._get(
            SEARCH_URL, {"q": address, "limit": 1, "addressdetails": 1}
        )
        if not isinstance(results, list) or not results:
            return None

        top = results[0]
        lat, lon = _as_float(top.get("lat")), _as_float(top.get("lon"))
        if lat is None or lon is None:
            return None
        return {
            "lat": lat,
            "lng": lon,
            "formatted_address": top.get("display_name") or address,
        }

    async def reverse_geocode(self, lat: float, lng: float) -> dict | None:
        """Coordinates to a formatted address."""
        payload = await self._get(
            REVERSE_URL, {"lat": lat, "lon": lng, "addressdetails": 1, "extratags": 1}
        )
        if not isinstance(payload, dict) or payload.get("error"):
            return None
        return {
            "lat": _as_float(payload.get("lat")) or lat,
            "lng": _as_float(payload.get("lon")) or lng,
            "formatted_address": payload.get("display_name") or "",
        }

    async def search_places(self, query: str, limit: int) -> list[dict]:
        """Free-text place search with full detail flags."""
        results = await self._get(
            SEARCH_URL,
            {
                "q": query,
                "limit": max(1, min(limit, MAX_SEARCH_RESULTS)),
                "addressdetails": 1,
                # `extratags` is where website/phone/opening_hours live; without
                # it a result is just a name and a point.
                "extratags": 1,
                "namedetails": 1,
            },
        )
        return results if isinstance(results, list) else []


class OpenStreetMapProvider:
    """Sources leads from Nominatim place search."""

    name = "OpenStreetMap"

    @property
    def is_configured(self) -> bool:
        """No API key exists for this service, so it is always available."""
        return bool(settings.OSM_USER_AGENT)

    def __init__(self) -> None:
        self._client = NominatimClient()

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        try:
            results = await self._client.search_places(query.full_text, query.max_results)
        except PermanentProviderError as exc:
            logger.warning("Nominatim rejected the request: %s", exc)
            return failed(self.name, str(exc))
        except TransientProviderError as exc:
            logger.warning("Nominatim temporarily unavailable: %s", exc)
            return failed(self.name, f"Temporarily unavailable: {exc}")

        leads = [lead for item in results if (lead := self._to_lead(item, query)) is not None]
        logger.info(
            "Nominatim returned %s result(s) for %r, %s usable as leads",
            len(results),
            query.full_text,
            len(leads),
        )
        return ProviderSearchResult(
            provider_name=self.name,
            status=ProviderRunStatus.COMPLETED,
            leads=leads[: query.max_results],
        )

    def _to_lead(self, item: dict, query: SearchQuery) -> NormalizedLead | None:
        # `extratags` carries the OSM tags; `address` is Nominatim's parsed form.
        tags = item.get("extratags") or {}
        address_parts = item.get("address") or {}
        fields = extract_osm_fields(tags)

        name = (
            item.get("name")
            or (item.get("namedetails") or {}).get("name")
            or fields["name"]
            # `display_name` leads with the place name, so its first component is
            # a reasonable last resort.
            or (item.get("display_name") or "").split(",")[0].strip()
        )
        if not name:
            return None

        # Nominatim's `category`/`type` describe the element the same way an OSM
        # tag pair would, so reuse the shared labeller for consistency.
        category, subcategory = osm_category({item.get("category", ""): item.get("type", "")})

        city = (
            fields["city"]
            or address_parts.get("city")
            or address_parts.get("town")
            or address_parts.get("village")
            or address_parts.get("state_district")
            or address_parts.get("county")
            or query.location
        )

        osm_type, osm_id = item.get("osm_type"), item.get("osm_id")
        return NormalizedLead(
            company_name=name,
            industry=query.industry or category,
            website=fields["website"],
            address=item.get("display_name") or fields["address"],
            city=city,
            country=address_parts.get("country") or fields["country"] or query.country,
            lat=_as_float(item.get("lat")),
            lng=_as_float(item.get("lon")),
            email=fields["email"],
            phone=fields["phone"] or fields["mobile"],
            tags=[t for t in [query.industry] if t],
            raw={
                "source": "OpenStreetMap (Nominatim)",
                "osm_type": osm_type,
                "osm_id": osm_id,
                "osm_element": f"{osm_type}/{osm_id}" if osm_type and osm_id else None,
                "place_id": item.get("place_id"),
                "category": category,
                "subcategory": subcategory,
                "street": fields["street"] or address_parts.get("road"),
                "area": fields["area"] or address_parts.get("suburb"),
                "district": fields["district"] or address_parts.get("state_district"),
                "state": fields["state"] or address_parts.get("state"),
                "postal_code": fields["postal_code"] or address_parts.get("postcode"),
                "mobile": fields["mobile"],
                "opening_hours": fields["opening_hours"],
                "operator": fields["operator"],
                "brand": fields["brand"],
                "wheelchair": fields["wheelchair"],
                "payment_methods": fields["payment_methods"] or None,
                "social": fields["social"] or None,
                # OSM data is ODbL-licensed; recording the attribution with the
                # lead keeps that obligation traceable to its source.
                "licence": item.get("licence"),
            },
            source_provider=self.name,
        )
