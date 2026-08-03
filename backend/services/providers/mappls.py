"""Mappls (MapmyIndia) adapter: OAuth, text search, autocomplete, nearby,
geocoding and reverse geocoding.

Mappls is India-focused and generally has better coverage of small Indian
businesses than Google Places, which is why it's worth having alongside it.

Authentication
--------------
OAuth2 client-credentials: exchange a client id/secret for a bearer token at
`https://outpost.mappls.com/api/security/oauth/token`, then send
`Authorization: Bearer <token>`. Tokens are long-lived (observed `expires_in`
~23h). `_TokenCache` keeps one token per client id in process memory and
refreshes it shortly before expiry, so a burst of searches performs a single
token exchange. A rejected token is evicted so the next call re-authenticates
instead of replaying a dead one.

The exchange sends the credentials as a form-encoded body (RFC 6749) rather
than in the query string, so the secret does not end up in proxy/access logs.
Both forms are accepted by Mappls; only one of them keeps the secret out of
URLs.

Response shape — what Mappls actually returns
---------------------------------------------
Verified against the live API:

    GET /api/places/textsearch/json?query=Restaurants in Ahmedabad&region=IND
    {"suggestedLocations": [
        {"placeName": "Apple Foods",
         "placeAddress": "Swami Vivekanand Road, Kagdapith, Raipur, "
                         "Ahmedabad, Gujarat, 380022",
         "eLoc": "ZKQFP8", "type": "POI", "keywords": ["FODOTH"],
         "distance": 42, "orderIndex": 1}, ...]}

Note what is **not** there: `latitude` / `longitude`. Mappls documents those
fields, but they are only populated for projects licensed for coordinate
delivery — on a project without that entitlement every Places response omits
them and the `advancedmaps/v1/geocode` endpoints answer `412 Precondition
Failed`. Leads sourced here therefore have no coordinates unless the project is
entitled, which is why `search()` logs a one-time warning naming the cause: a
silent absence of map pins is otherwise very hard to diagnose.

City/state/pincode are likewise absent as discrete fields, so they are derived
from `placeAddress` via `services.enrichment.address.parse_address` — the same
parser the CSV importer uses, so an address yields the same city whichever door
it came through.
"""

from __future__ import annotations

import logging
import time

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

logger = logging.getLogger("leadmaster.providers.mappls")

TOKEN_URL = "https://outpost.mappls.com/api/security/oauth/token"
TEXT_SEARCH_URL = "https://atlas.mappls.com/api/places/textsearch/json"
AUTOCOMPLETE_URL = "https://atlas.mappls.com/api/places/search/json"
NEARBY_URL = "https://atlas.mappls.com/api/places/nearby/json"
GEOCODE_URL = "https://atlas.mappls.com/api/places/geocode"
REVERSE_GEOCODE_URL = "https://apis.mappls.com/advancedmaps/v1/rev_geocode"

# Refresh a little before actual expiry so an in-flight request can't use a
# token that expires mid-call.
_TOKEN_SAFETY_WINDOW_SECONDS = 60

# Mappls mixes administrative entries into the same `suggestedLocations` array
# as businesses — a query for "Restaurants in Ahmedabad" also returns a CITY row
# named "Ahmedabad". Turning that into a lead would be fabrication.
#
# Deny-listing the administrative types rather than allow-listing "POI": Mappls
# can introduce new POI subtypes, and dropping a real business is worse than
# occasionally keeping an unfamiliar row.
_ADMINISTRATIVE_TYPES = {
    "CITY",
    "STATE",
    "DISTRICT",
    "SUBDISTRICT",
    "LOCALITY",
    "SUBLOCALITY",
    "SUBSUBLOCALITY",
    "VILLAGE",
    "STREET",
    "PINCODE",
    "HOUSE_NUMBER",
    "HOUSE_NAME",
}


class MapplsAuthError(PermanentProviderError):
    """Credentials were rejected, or the project lacks the requested API."""


class _TokenCache:
    """Process-level `{client_id: (token, expires_at_epoch)}` cache.

    A shared cache in Redis would avoid one exchange per worker process; with
    per-process caching the worst case is one extra token request per worker
    per ~23 hours, which is not worth the added dependency.
    """

    _tokens: dict[str, tuple[str, float]] = {}

    @classmethod
    def get(cls, client_id: str) -> str | None:
        cached = cls._tokens.get(client_id)
        if cached and cached[1] > time.time() + _TOKEN_SAFETY_WINDOW_SECONDS:
            return cached[0]
        return None

    @classmethod
    def put(cls, client_id: str, token: str, expires_in: int) -> None:
        cls._tokens[client_id] = (token, time.time() + expires_in)

    @classmethod
    def evict(cls, client_id: str) -> None:
        cls._tokens.pop(client_id, None)


class MapplsClient:
    """Authenticated access to the Mappls REST APIs.

    Split out from `MapplsProvider` so the geocoding endpoints can be used by
    `services/maps_service.py` without dragging in the lead-search machinery.
    """

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        # `or` rather than a default argument: settings are read at call time,
        # so tests that monkeypatch credentials take effect.
        self.client_id = client_id or settings.MAPPLS_CLIENT_ID
        self.client_secret = client_secret or settings.MAPPLS_CLIENT_SECRET

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def token(self) -> str:
        cached = _TokenCache.get(self.client_id)
        if cached:
            return cached

        logger.info("Requesting a new Mappls OAuth token (client_id=%s)", _mask(self.client_id))
        payload, _ = await request_json(
            "POST",
            TOKEN_URL,
            form_body={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )

        token = payload.get("access_token")
        if not token:
            raise MapplsAuthError(
                f"Mappls token response contained no access_token: {_summarize(payload)}"
            )

        expires_in = _as_int(payload.get("expires_in")) or 3600
        _TokenCache.put(self.client_id, token, expires_in)
        logger.info("Mappls token acquired, valid for %ss (scope=%s)", expires_in, payload.get("scope"))
        return token

    async def get(self, url: str, params: dict) -> tuple[dict, int]:
        """Authenticated GET. Evicts the cached token on an auth rejection."""
        token = await self.token()
        try:
            return await request_json(
                "GET", url, params=params, headers={"Authorization": f"Bearer {token}"}
            )
        except PermanentProviderError:
            _TokenCache.evict(self.client_id)
            raise

    # --- Geocoding ------------------------------------------------------

    async def geocode(self, address: str) -> dict | None:
        """Forward geocode. Returns None when Mappls has no match.

        Raises `MapplsAuthError` when the project is not licensed to return
        coordinates — the caller can then fall back to another provider rather
        than silently reporting "no results" for an address that does exist.
        """
        payload, _ = await self.get(GEOCODE_URL, {"address": address, "itemCount": 1})
        result = payload.get("copResults")
        if not result:
            return None

        lat = _as_float(result.get("latitude") or result.get("lat"))
        lng = _as_float(result.get("longitude") or result.get("lng"))
        if lat is None or lng is None:
            raise MapplsAuthError(
                "Mappls geocoding returned no coordinates — this project is not licensed for "
                f"coordinate delivery. Response: {_summarize(payload)}"
            )

        return {
            "lat": lat,
            "lng": lng,
            "formatted_address": result.get("formattedAddress") or address,
        }

    async def reverse_geocode(self, lat: float, lng: float) -> dict | None:
        """Reverse geocode coordinates to a formatted address."""
        payload, _ = await self.get(REVERSE_GEOCODE_URL, {"lat": lat, "lng": lng})
        results = payload.get("results") or []
        if not results:
            return None

        top = results[0]
        return {
            # Mappls echoes the query coordinates back as strings.
            "lat": _as_float(top.get("lat")) if top.get("lat") is not None else lat,
            "lng": _as_float(top.get("lng")) if top.get("lng") is not None else lng,
            "formatted_address": top.get("formatted_address") or "",
        }

    async def nearby(self, lat: float, lng: float, radius_meters: int, keyword: str | None) -> list[dict]:
        """POI search around a point. Returns Mappls' `suggestedLocations`."""
        params: dict[str, str | int] = {
            "refLocation": f"{lat},{lng}",
            "radius": radius_meters,
            # Mappls requires a keyword; "" returns 204 rather than everything.
            "keywords": keyword or "POI",
        }
        payload, _ = await self.get(NEARBY_URL, params)
        return payload.get("suggestedLocations") or []

    async def autocomplete(self, query: str, lat: float | None = None, lng: float | None = None) -> list[dict]:
        """Type-ahead place suggestions, optionally biased to a location."""
        params: dict[str, str] = {"query": query, "region": "IND"}
        if lat is not None and lng is not None:
            params["location"] = f"{lat},{lng}"
        payload, _ = await self.get(AUTOCOMPLETE_URL, params)
        return payload.get("suggestedLocations") or []


class MapplsProvider:
    """Sources Indian business leads from Mappls text search."""

    name = "Mappls (MapmyIndia)"

    # Logged once per process: repeating it for every search would bury the
    # rest of the provider log without telling the operator anything new.
    _warned_about_missing_coordinates = False

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self._client = MapplsClient(client_id, client_secret)

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        if not self.is_configured:
            return skipped(self.name, "MAPPLS_CLIENT_ID / MAPPLS_CLIENT_SECRET are not configured")

        params = {"query": query.full_text, "region": "IND"}

        try:
            payload, latency_ms = await self._client.get(TEXT_SEARCH_URL, params)
        except PermanentProviderError as exc:
            logger.warning("Mappls text search rejected: %s", exc)
            return failed(self.name, str(exc))
        except TransientProviderError as exc:
            logger.warning("Mappls text search temporarily unavailable: %s", exc)
            return failed(self.name, f"Temporarily unavailable: {exc}")

        suggestions = payload.get("suggestedLocations") or payload.get("results") or []
        leads = [
            lead
            for item in suggestions
            if (lead := self._to_lead(item, query)) is not None
        ]

        logger.info(
            "Mappls returned %s suggestion(s) for %r, %s usable as leads (%sms)",
            len(suggestions),
            query.full_text,
            len(leads),
            latency_ms,
        )
        self._warn_if_no_coordinates(leads)

        return ProviderSearchResult(
            provider_name=self.name,
            status=ProviderRunStatus.COMPLETED,
            leads=leads[: query.max_results],
            latency_ms=latency_ms,
        )

    def _warn_if_no_coordinates(self, leads: list[NormalizedLead]) -> None:
        if not leads or type(self)._warned_about_missing_coordinates:
            return
        if any(lead.lat is not None and lead.lng is not None for lead in leads):
            return

        type(self)._warned_about_missing_coordinates = True
        logger.warning(
            "Mappls returned %s lead(s) with no coordinates. Mappls only populates "
            "latitude/longitude for projects licensed for coordinate delivery, so these "
            "leads cannot be plotted on the map. Enable coordinate delivery on the Mappls "
            "project, or configure GOOGLE_MAPS_API_KEY, to get map pins.",
            len(leads),
        )

    def _to_lead(self, item: dict, query: SearchQuery) -> NormalizedLead | None:
        name = item.get("placeName") or item.get("poi") or item.get("name")
        if not name:
            return None

        # Administrative entries (CITY / STATE / LOCALITY) share the results
        # array with businesses and are not companies.
        if (item.get("type") or "").upper() in _ADMINISTRATIVE_TYPES:
            return None

        address = item.get("placeAddress") or ""
        parsed = parse_address(address)
        # Licensed projects return discrete city/state fields; unlicensed ones
        # only have the address string. Prefer the explicit values when present.
        city = item.get("city") or item.get("district") or parsed.city
        state = item.get("state") or parsed.state
        pincode = parsed.postal_code

        return NormalizedLead(
            company_name=name,
            industry=query.industry,
            # Mappls has no discrete city field; fall back to the searched
            # location so the lead is still filterable by city.
            city=city or query.location,
            country="India",  # Mappls is an India-only dataset
            lat=_as_float(item.get("latitude") or item.get("lat")),
            lng=_as_float(item.get("longitude") or item.get("lng") or item.get("lon")),
            address=address or None,
            phone=item.get("mobileNo") or item.get("phone"),
            tags=[t for t in [query.industry] if t],
            raw={
                "eloc": item.get("eLoc"),
                "address": address,
                "state": state,
                "pincode": pincode,
                "mappls_type": item.get("type"),
                "mappls_keywords": item.get("keywords"),
            },
            source_provider=self.name,
        )


def _mask(value: str | None) -> str:
    """Enough of a credential to correlate log lines, not enough to reuse."""
    if not value:
        return "<unset>"
    return f"{value[:6]}...({len(value)} chars)"


def _summarize(payload: dict, limit: int = 300) -> str:
    """Short, log-safe rendering of a provider response body."""
    return str(payload)[:limit]


def _as_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
