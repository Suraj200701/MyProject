"""Google Maps integration: geocoding, reverse geocoding, nearby places, and
distance matrix — plus a pure-math haversine helper that needs no API key.

Every function that calls out to Google guards on `settings.GOOGLE_MAPS_API_KEY`
being set and raises `BadRequestError` immediately (rather than firing a
doomed HTTP request) when it isn't. `haversine_distance_km` is the one
exception: it's plain math and always works, which is why it's what the org's
own lead radius-filtering (see api/v1/map.py::nearby_leads) is built on
instead of the (slower, metered) Distance Matrix API.
"""

import math

import httpx

from config.settings import settings
from utils.exceptions import BadRequestError

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

EARTH_RADIUS_KM = 6371.0088


def _require_api_key() -> None:
    if not settings.GOOGLE_MAPS_API_KEY:
        raise BadRequestError("Google Maps is not configured — set GOOGLE_MAPS_API_KEY in .env")


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
    """Resolves a free-text address/city into coordinates via Google's
    Geocoding API. Returns None if Google found no results. Requires
    GOOGLE_MAPS_API_KEY."""
    _require_api_key()

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


async def reverse_geocode(lat: float, lng: float) -> dict | None:
    """Resolves coordinates into a formatted address via Google's Geocoding
    API. Returns None if Google found no results. Requires
    GOOGLE_MAPS_API_KEY."""
    _require_api_key()

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


async def nearby_search(lat: float, lng: float, radius_meters: int, keyword: str | None = None) -> list[dict]:
    """Real call to Google's Places Nearby Search API. Requires
    GOOGLE_MAPS_API_KEY."""
    _require_api_key()

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
    data = response.json()

    return data.get("results") or []


async def distance_matrix(origin: tuple[float, float], destinations: list[tuple[float, float]]) -> list[dict]:
    """Real call to Google's Distance Matrix API for batch true-road
    distances/durations. Requires GOOGLE_MAPS_API_KEY.

    Unlike `haversine_distance_km`, this reflects actual road routing (and
    costs a metered API call), so it's exposed as its own endpoint rather
    than used for the org's bulk lead radius-filtering.
    """
    _require_api_key()

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
