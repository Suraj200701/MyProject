"""Geocoding, reverse geocoding, nearby places and distance matrix.

Provider selection
------------------
Three backends are supported, tried in order:

  1. **Google Maps** — used when `GOOGLE_MAPS_API_KEY` is set. Global coverage.
  2. **Geoapify** — used when `GEOAPIFY_API_KEY` is set. OpenStreetMap-derived,
     global, and returns real coordinates for both forward and reverse geocoding.
  3. **Mappls (MapmyIndia)** — used when `MAPPLS_CLIENT_ID`/`MAPPLS_CLIENT_SECRET`
     are set. India-only, and see the entitlement note below.
  4. **OpenStreetMap / Nominatim** — always available: it needs no API key, only
     an identifying User-Agent. This is why geocoding now works on a completely
     unconfigured deployment. It is last because it is donated infrastructure
     rate-limited to 1 request/second, so a paid provider is preferred when one
     is configured.

Geoapify sits ahead of Mappls deliberately: Mappls forward geocoding needs an
entitlement many projects do not have, whereas Geoapify answers with coordinates
on the free tier. Google stays first where a key exists, since it has the richest
place data.

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
from services.providers.geoapify import GeoapifyClient
from services.providers.openstreetmap import NominatimClient
from services.providers.mappls import MapplsClient
from utils.exceptions import BadRequestError

logger = logging.getLogger("leadmaster.maps")

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

EARTH_RADIUS_KM = 6371.0088

_NO_PROVIDER = (
    "No geocoding provider is available — set OSM_USER_AGENT (OpenStreetMap needs "
    "no key), GEOAPIFY_API_KEY, GOOGLE_MAPS_API_KEY, or MAPPLS_CLIENT_ID and "
    "MAPPLS_CLIENT_SECRET, in .env"
)


def _google_configured() -> bool:
    return bool(settings.GOOGLE_MAPS_API_KEY)


def _geoapify() -> GeoapifyClient | None:
    client = GeoapifyClient()
    return client if client.is_configured else None


def _mappls() -> MapplsClient | None:
    client = MapplsClient()
    return client if client.is_configured else None


def _nominatim() -> NominatimClient | None:
    """Always available unless the User-Agent has been blanked out."""
    client = NominatimClient()
    return client if client.is_configured else None


def _require_any_provider() -> None:
    if (
        not _google_configured()
        and _geoapify() is None
        and _mappls() is None
        and _nominatim() is None
    ):
        raise BadRequestError(_NO_PROVIDER)


async def _attempt(label: str, awaitable):
    """Runs one provider call, translating provider errors into 400s.

    Deliberately does **not** fall through to the next provider on failure: a
    misconfigured primary silently shifting to a secondary with different data
    quality is far harder to diagnose than a clear error naming the provider that
    said no.
    """
    try:
        return await awaitable
    except PermanentProviderError as exc:
        logger.warning("%s call failed: %s", label, exc)
        raise BadRequestError(f"{label} is unavailable: {exc}") from exc
    except TransientProviderError as exc:
        raise BadRequestError(f"{label} is temporarily unavailable: {exc}") from exc


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

    geoapify = _geoapify()
    if geoapify is not None:
        return await _attempt("Geoapify geocoding", geoapify.geocode(address))

    mappls = _mappls()
    if mappls is not None:
        return await _attempt("Mappls geocoding", mappls.geocode(address))

    osm = _nominatim()
    assert osm is not None  # guaranteed by _require_any_provider
    return await _attempt("OpenStreetMap geocoding", osm.geocode(address))


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

    geoapify = _geoapify()
    if geoapify is not None:
        return await _attempt("Geoapify reverse geocoding", geoapify.reverse_geocode(lat, lng))

    mappls = _mappls()
    if mappls is not None:
        return await _attempt("Mappls reverse geocoding", mappls.reverse_geocode(lat, lng))

    osm = _nominatim()
    assert osm is not None
    return await _attempt("OpenStreetMap reverse geocoding", osm.reverse_geocode(lat, lng))


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

    geoapify = _geoapify()
    if geoapify is not None:
        from services.providers.geoapify import categories_for

        # Geoapify Places needs a category, not free text. An unrecognised
        # keyword falls back to `commercial` here (unlike lead search, which
        # skips): the caller asked for "what is near this point", so a broad
        # answer is useful rather than misleading.
        categories = categories_for(keyword or "") or ("commercial",)
        features = await _attempt(
            "Geoapify nearby search",
            geoapify.places_in_circle(categories, lat, lng, radius_meters, 20),
        )
        return [
            {
                "name": props.get("name") or props.get("address_line1"),
                "address": props.get("formatted"),
                "lat": _as_float(props.get("lat")),
                "lng": _as_float(props.get("lon")),
                "source": "geoapify",
            }
            for props in ((f.get("properties") or {}) for f in features)
        ]

    client = _mappls()
    assert client is not None
    places = await _attempt(
        "Mappls nearby search", client.nearby(lat, lng, radius_meters, keyword)
    )

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
    """Type-ahead place suggestions, from Geoapify or Mappls.

    Google's Places Autocomplete is a separately billed product this deployment
    does not use, so it is not part of the chain here.
    """
    geoapify = _geoapify()
    if geoapify is not None:
        # Already normalized to {name, address, lat, lng, type} by the client.
        return await _attempt("Geoapify autocomplete", geoapify.autocomplete(query))

    client = _mappls()
    if client is None:
        raise BadRequestError(
            "Place autocomplete requires GEOAPIFY_API_KEY, or MAPPLS_CLIENT_ID and "
            "MAPPLS_CLIENT_SECRET, in .env"
        )

    suggestions = await _attempt("Mappls autocomplete", client.autocomplete(query, lat, lng))

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
