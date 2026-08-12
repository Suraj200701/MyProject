"""Google Maps Extractor — viewport-scoped business collection, official API only.

What this reproduces
--------------------
The useful behaviour of a Maps extractor: type a keyword and an area, get the
businesses there, move the map and collect more, never storing the same business
twice. It is implemented entirely on **Places API (New) `searchText`**.

Why no scraping is needed
-------------------------
`searchText` accepts a `locationRestriction` rectangle, so "the businesses in the
area currently on screen" is a documented API parameter, not something that has
to be read off a rendered map. Panning the map is just another request with new
bounds. Measured against this account: a Bhopal rectangle returned 10 businesses,
a Mandideep rectangle returned 5, with zero overlap — five genuinely new leads
from moving the map, deduplicated by Place ID for free.

Nothing here reads Google's HTML, uses a private endpoint, rotates proxies or
works around a rate limit. The key is sent as a header from the server; it never
reaches a browser.

Limits that come from the API, not from us
------------------------------------------
`searchText` returns at most 20 results per request and does not paginate beyond
that, which is precisely why viewport movement matters: covering a city means
several smaller rectangles rather than one big page-through.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import settings
from services.providers.base import NormalizedLead
from services.providers.google_places import MAX_RESULT_COUNT, SEARCH_TEXT_URL
from services.providers.http import (
    PermanentProviderError,
    TransientProviderError,
    request_json,
)

logger = logging.getLogger("leadmaster.providers.gmaps_extractor")

PROVIDER_NAME = "Google Maps Extractor"

# Everything the extractor surfaces. Each entry can raise the billing SKU, so
# this is the full set the feature actually displays and nothing beyond it.
EXTRACTOR_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.addressComponents",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.googleMapsUri",
        "places.primaryTypeDisplayName",
        "places.types",
        "places.regularOpeningHours",
        "places.businessStatus",
    ]
)


@dataclass(frozen=True)
class Viewport:
    """The map rectangle to search inside."""

    south: float
    west: float
    north: float
    east: float

    def as_restriction(self) -> dict:
        return {
            "rectangle": {
                "low": {"latitude": self.south, "longitude": self.west},
                "high": {"latitude": self.north, "longitude": self.east},
            }
        }


class GoogleMapsExtractor:
    """Collects public Google Maps business listings via the official API."""

    name = PROVIDER_NAME

    def __init__(self, api_key: str | None = None) -> None:
        # Read at call time, matching every other client here, so tests can
        # monkeypatch settings.
        self._api_key = api_key or settings.GOOGLE_MAPS_API_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def collect(
        self,
        *,
        keywords: list[str],
        location: str | None = None,
        viewport: Viewport | None = None,
        max_results: int = MAX_RESULT_COUNT,
    ) -> tuple[list[NormalizedLead], list[str]]:
        """Runs one search per keyword and returns (leads, errors).

        Keywords are searched separately because Places ranks a single blended
        query rather than unioning the terms — "electrical panel, control panel"
        as one string returns fewer distinct businesses than the two run apart.

        Deduplication by Place ID happens here so repeated keywords and
        overlapping viewports cannot produce the same business twice.
        """
        if not self.is_configured:
            return [], ["Google Places is not configured."]

        leads: list[NormalizedLead] = []
        errors: list[str] = []
        seen: set[str] = set()

        for keyword in keywords:
            term = keyword.strip()
            if not term:
                continue

            body: dict = {
                # With a viewport the text stays a pure keyword: appending the
                # place name as well biases results back towards the named city
                # and undoes the point of panning the map.
                "textQuery": term if viewport else " ".join(p for p in [term, location] if p),
                "maxResultCount": min(max_results, MAX_RESULT_COUNT),
            }
            if viewport is not None:
                body["locationRestriction"] = viewport.as_restriction()

            try:
                payload, _latency = await request_json(
                    "POST",
                    SEARCH_TEXT_URL,
                    json_body=body,
                    headers={
                        "X-Goog-Api-Key": self._api_key,
                        "X-Goog-FieldMask": EXTRACTOR_FIELD_MASK,
                        "Content-Type": "application/json",
                    },
                )
            except (PermanentProviderError, TransientProviderError) as exc:
                # One keyword failing must not lose the others' results.
                logger.warning("Maps extraction failed for %r: %s", term, exc)
                errors.append(f"{term}: {exc}"[:200])
                continue

            for place in payload.get("places") or []:
                place_id = place.get("id")
                if place_id and place_id in seen:
                    continue
                if place_id:
                    seen.add(place_id)
                lead = self._to_lead(place, keyword=term, location=location)
                if lead is not None:
                    leads.append(lead)

        return leads, errors

    def _to_lead(self, place: dict, *, keyword: str, location: str | None) -> NormalizedLead | None:
        """Maps a Place to a NormalizedLead, inventing nothing.

        Absent fields stay absent: Places omits `websiteUri` for businesses that
        have not supplied one, and a guessed domain would be worse than a blank.
        """
        name = (place.get("displayName") or {}).get("text")
        if not name:
            return None

        loc = place.get("location") or {}
        components = {
            tuple(c.get("types") or []): c.get("longText")
            for c in (place.get("addressComponents") or [])
        }

        def component(kind: str) -> str | None:
            for types, value in components.items():
                if kind in types:
                    return value
            return None

        hours = place.get("regularOpeningHours") or {}

        return NormalizedLead(
            company_name=name,
            industry=(place.get("primaryTypeDisplayName") or {}).get("text")
            or (place.get("types") or [None])[0],
            website=place.get("websiteUri"),
            address=place.get("formattedAddress"),
            city=component("locality") or component("administrative_area_level_2"),
            country=component("country"),
            lat=loc.get("latitude"),
            lng=loc.get("longitude"),
            rating=place.get("rating"),
            phone=place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
            tags=["Google Maps"],
            raw={
                "place_id": place.get("id"),
                "google_maps_url": place.get("googleMapsUri"),
                "review_count": place.get("userRatingCount"),
                "business_status": place.get("businessStatus"),
                "opening_hours": hours.get("weekdayDescriptions"),
                "types": place.get("types"),
                # Recorded so enrichment can later say a contact came from the
                # company's own website rather than from Maps.
                "source_api": "places_text_search",
                "search_keyword": keyword,
                "search_location": location,
            },
            source_provider=PROVIDER_NAME,
        )
