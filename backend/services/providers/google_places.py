"""Google Places API (New) — Text Search adapter.

Uses the **current** Places API (New) `searchText` endpoint
(`POST https://places.googleapis.com/v1/places:searchText`), not the legacy
`maps.googleapis.com/maps/api/place/textsearch/json` endpoint, which Google has
deprecated for new projects.

Two details specific to this API that are easy to get wrong:

* **The field mask is mandatory.** Places API (New) requires an
  `X-Goog-FieldMask` header; omitting it returns 400. It also determines
  billing tier, so requesting only what we persist keeps cost at the lowest
  applicable SKU rather than paying for fields we discard.
* **`maxResultCount` caps at 20** per request. We clamp to it so an over-large
  `max_results` doesn't produce a 400.

This adapter populates `lat`/`lng` from `location`, which is what makes the
Map Search page work for searched leads (previously always empty).
"""

from __future__ import annotations

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

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
MAX_RESULT_COUNT = 20

# Only the fields we actually store. Each addition can move the request into a
# more expensive billing SKU, so this list is deliberately minimal.
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.addressComponents",
        "places.location",
        "places.rating",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.primaryTypeDisplayName",
        "places.businessStatus",
    ]
)


class GooglePlacesProvider:
    """Sources business leads from Google Places text search."""

    name = "Google Places"

    def __init__(self, api_key: str | None = None):
        # An explicit key (from ApiProvider.api_key_encrypted) wins over the
        # shared platform key in settings.
        self._api_key = api_key or settings.GOOGLE_MAPS_API_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        if not self.is_configured:
            return skipped(self.name, "GOOGLE_MAPS_API_KEY is not configured")

        body: dict = {
            "textQuery": query.full_text,
            "maxResultCount": max(1, min(query.max_results, MAX_RESULT_COUNT)),
        }
        if query.country:
            # Places expects a 2-letter region code; skip anything else rather
            # than sending a value the API will reject.
            region = _country_to_region_code(query.country)
            if region:
                body["regionCode"] = region

        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": FIELD_MASK,
            "Content-Type": "application/json",
        }

        try:
            payload, latency_ms = await request_json("POST", SEARCH_TEXT_URL, json_body=body, headers=headers)
        except PermanentProviderError as exc:
            return failed(self.name, str(exc))
        except TransientProviderError as exc:
            return failed(self.name, f"Temporarily unavailable: {exc}")

        leads = [
            lead
            for place in payload.get("places", [])
            if (lead := self._to_lead(place, query)) is not None
        ]
        return ProviderSearchResult(
            provider_name=self.name,
            status=ProviderRunStatus.COMPLETED,
            leads=leads[: query.max_results],
            latency_ms=latency_ms,
        )

    def _to_lead(self, place: dict, query: SearchQuery) -> NormalizedLead | None:
        name = (place.get("displayName") or {}).get("text")
        if not name:
            return None  # a place without a name is not a usable lead

        # Permanently closed businesses are noise in a sales pipeline.
        if place.get("businessStatus") == "CLOSED_PERMANENTLY":
            return None

        location = place.get("location") or {}
        city, country = _city_country_from_components(
            place.get("addressComponents") or [], place.get("formattedAddress") or ""
        )

        return NormalizedLead(
            company_name=name,
            industry=query.industry or (place.get("primaryTypeDisplayName") or {}).get("text"),
            website=place.get("websiteUri"),
            city=city or query.location,
            country=country or query.country,
            lat=location.get("latitude"),
            lng=location.get("longitude"),
            rating=place.get("rating"),
            phone=place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
            tags=[t for t in [query.industry] if t],
            raw={"place_id": place.get("id"), "formatted_address": place.get("formattedAddress")},
            source_provider=self.name,
        )


def _city_country_from_components(components: list[dict], formatted_address: str) -> tuple[str | None, str | None]:
    """Pulls city/country from structured address components.

    Falls back to the tail of the formatted address, because `locality` is
    absent for many non-US addresses (Indian addresses in particular often
    carry the city in `administrative_area_level_2`).
    """
    city = None
    country = None
    for component in components:
        types = component.get("types") or []
        if country is None and "country" in types:
            country = component.get("longText") or component.get("shortText")
        if city is None and "locality" in types:
            city = component.get("longText") or component.get("shortText")
        if city is None and "administrative_area_level_2" in types:
            city = component.get("longText") or component.get("shortText")
        if city is None and "postal_town" in types:
            city = component.get("longText")

    if (city is None or country is None) and formatted_address:
        parts = [p.strip() for p in formatted_address.split(",") if p.strip()]
        if country is None and parts:
            country = parts[-1]
        if city is None and len(parts) >= 3:
            city = parts[-3]

    return city, country


_COUNTRY_REGION_CODES = {
    "india": "IN",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "uae": "AE",
    "united arab emirates": "AE",
    "singapore": "SG",
    "indonesia": "ID",
    "australia": "AU",
    "canada": "CA",
    "germany": "DE",
}


def _country_to_region_code(country: str) -> str | None:
    value = (country or "").strip()
    if len(value) == 2 and value.isalpha():
        return value.upper()
    return _COUNTRY_REGION_CODES.get(value.lower())
