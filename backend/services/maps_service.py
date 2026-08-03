"""Geocoding, reverse geocoding, nearby places and distance matrix.

Provider selection
------------------
Two backends are supported, tried in order:

  1. **Google Maps** — used when `GOOGLE_MAPS_API_KEY` is set. Global coverage.
  2. **Mappls (MapmyIndia)** — used when `MAPPLS_CLIENT_ID`/`MAPPLS_CLIENT_SECRET`
     are set. India-only, but it is what many Indian deployments actually have.

Previously every function here required a Google key, so a deployment
configured with Mappls alone got `400 Google Maps is not configured` from the
whole Map page even though a working geocoding provider was present.

Mappls entitlements
-------------------
Mappls sells coordinate delivery separately from place search. On a project
without it, Places responses omit `latitude`/`longitude` and the geocoding
endpoints answer `412`. `MapplsClient.geocode` raises `MapplsAuthError` in that
case rather than reporting "no results", and the functions below turn it into a
`BadRequestError` that names the cause — an operator seeing "address not found"
for an address that plainly exists would have no way to diagnose it otherwise.

`haversine_distance_km` is the one function that needs no provider at all: it's
plain math, which is why the org's own lead radius-filtering
(`api/v1/map.py::nearby_leads`) is built on it instead of the metered Distance
Matrix API.
"""

import logging
import math

import httpx

from config.settings import settings
from services.providers.http import PermanentProviderError, TransientProviderError
from services.providers.mappls import MapplsClient
from utils.exceptions import BadRequestError

logger = logging.getLogger("leadmaster.maps")

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

EARTH_RADIUS_KM = 6371.0088

_NO_PROVIDER = (
    "No geocoding provider is configured — set GOOGLE_MAPS_API_KEY, or "
    "MAPPLS_CLIENT_ID and MAPPLS_CLIENT_SECRET, in .env"
)


def _google_configured() -> bool:
    return bool(settings.GOOGLE_MAPS_API_KEY)


def _mappls() -> MapplsClient | None:
    client = MapplsClient()
    return client if client.is_configured else None


def _require_any_provider() -> None:
    if not _google_configured() and _mappls() is None:
        raise BadRequestError(_NO_PROVIDER)


def _require_google(feature: str) -> None:
    if not _google_configured():
        raise BadRequestError(f"{feature} requires GOOGLE_MAPS_API_KEY — Mappls has no equivalent endpoint")


def haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in kilometers.

    Pure math — no network call, no API key required. This is what
    `/map/nearby-leads` uses to filter the org's own leads by radius.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


async def geocode_address(address: str) -> dict | None:
    """Resolves a free-text address/city into coordinates.

    Returns None when the provider genuinely found nothing. Raises
    `BadRequestError` when no provider is configured, or when the configured
    provider cannot return coordinates.
    """
    _require_any_provider()

    if _google_configured():
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                GEOCODE_URL,
                params={"address": address, "key": settings.GOOGLE_MAPS_API_KEY},
            )
        response.raise_for_status()
        data = response.json()

        results = data.get("results") or []
        if not results:
            return None

        location = results[0]["geometry"]["location"]
        return {
            "lat": location["lat"],
            "lng": location["lng"],
            "formatted_address": results[0].get("formatted_address", address),
        }

    client = _mappls()
    assert client is not None  # guaranteed by _require_any_provider
    try:
        return await client.geocode(address)
    except PermanentProviderError as exc:
        logger.warning("Mappls geocode failed for %r: %s", address, exc)
        raise BadRequestError(f"Mappls geocoding is unavailable: {exc}") from exc
    except TransientProviderError as exc:
        raise BadRequestError(f"Mappls geocoding is temporarily unavailable: {exc}") from exc


async def reverse_geocode(lat: float, lng: float) -> dict | None:
    """Resolves coordinates into a formatted address."""
    _require_any_provider()

    if _google_configured():
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                GEOCODE_URL,
                params={"latlng": f"{lat},{lng}", "key": settings.GOOGLE_MAPS_API_KEY},
            )
        response.raise_for_status()
        data = response.json()

        results = data.get("results") or []
        if not results:
            return None

        location = results[0]["geometry"]["location"]
        return {
            "lat": location["lat"],
            "lng": location["lng"],
            "formatted_address": results[0].get("formatted_address", ""),
        }

    client = _mappls()
    assert client is not None
    try:
        return await client.reverse_geocode(lat, lng)
    except PermanentProviderError as exc:
        logger.warning("Mappls reverse geocode failed for %s,%s: %s", lat, lng, exc)
        raise BadRequestError(f"Mappls reverse geocoding is unavailable: {exc}") from exc
    except TransientProviderError as exc:
        raise BadRequestError(f"Mappls reverse geocoding is temporarily unavailable: {exc}") from exc


async def nearby_search(lat: float, lng: float, radius_meters: int, keyword: str | None = None) -> list[dict]:
    """Places near a point, from whichever provider is configured.

    Google returns its own `results` shape; Mappls returns `suggestedLocations`.
    Both are normalized to `{name, address, lat, lng, source}` so the caller
    doesn't branch on which provider answered.
    """
    _require_any_provider()

    if _google_configured():
        params: dict[str, str | int] = {
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "key": settings.GOOGLE_MAPS_API_KEY,
        }
        if keyword:
            params["keyword"] = keyword

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(PLACES_NEARBY_URL, params=params)
        response.raise_for_status()

        return [
            {
                "name": place.get("name"),
                "address": place.get("vicinity") or place.get("formatted_address"),
                "lat": (place.get("geometry") or {}).get("location", {}).get("lat"),
                "lng": (place.get("geometry") or {}).get("location", {}).get("lng"),
                "source": "google",
            }
            for place in (response.json().get("results") or [])
        ]

    client = _mappls()
    assert client is not None
    try:
        places = await client.nearby(lat, lng, radius_meters, keyword)
    except PermanentProviderError as exc:
        logger.warning("Mappls nearby search failed at %s,%s: %s", lat, lng, exc)
        raise BadRequestError(f"Mappls nearby search is unavailable: {exc}") from exc
    except TransientProviderError as exc:
        raise BadRequestError(f"Mappls nearby search is temporarily unavailable: {exc}") from exc

    return [
        {
            "name": place.get("placeName"),
            "address": place.get("placeAddress"),
            # Present only on projects licensed for coordinate delivery.
            "lat": _as_float(place.get("latitude")),
            "lng": _as_float(place.get("longitude")),
            "source": "mappls",
        }
        for place in places
    ]


async def autocomplete(query: str, lat: float | None = None, lng: float | None = None) -> list[dict]:
    """Type-ahead place suggestions. Mappls only — Google's Places Autocomplete
    is a separately billed product this deployment does not use."""
    client = _mappls()
    if client is None:
        raise BadRequestError(
            "Place autocomplete requires MAPPLS_CLIENT_ID and MAPPLS_CLIENT_SECRET in .env"
        )

    try:
        suggestions = await client.autocomplete(query, lat, lng)
    except PermanentProviderError as exc:
        logger.warning("Mappls autocomplete failed for %r: %s", query, exc)
        raise BadRequestError(f"Mappls autocomplete is unavailable: {exc}") from exc
    except TransientProviderError as exc:
        raise BadRequestError(f"Mappls autocomplete is temporarily unavailable: {exc}") from exc

    return [
        {
            "name": item.get("placeName"),
            "address": item.get("placeAddress"),
            "type": item.get("type"),
            "eloc": item.get("eLoc"),
            "lat": _as_float(item.get("latitude")),
            "lng": _as_float(item.get("longitude")),
        }
        for item in suggestions
    ]


async def distance_matrix(origin: tuple[float, float], destinations: list[tuple[float, float]]) -> list[dict]:
    """Batch true-road distances/durations via Google's Distance Matrix API.

    Unlike `haversine_distance_km`, this reflects actual road routing (and
    costs a metered API call), so it's exposed as its own endpoint rather
    than used for the org's bulk lead radius-filtering. Google-only: Mappls'
    equivalent is a separate product this deployment does not integrate.
    """
    _require_google("Distance matrix")

    if not destinations:
        return []

    origin_param = f"{origin[0]},{origin[1]}"
    destinations_param = "|".join(f"{d_lat},{d_lng}" for d_lat, d_lng in destinations)

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            DISTANCE_MATRIX_URL,
            params={
                "origins": origin_param,
                "destinations": destinations_param,
                "key": settings.GOOGLE_MAPS_API_KEY,
            },
        )
    response.raise_for_status()
    data = response.json()

    rows = data.get("rows") or []
    if not rows:
        return []

    return rows[0].get("elements") or []


def _as_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
