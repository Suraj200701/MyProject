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
from datetime import UTC, datetime

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
# Reused rather than reimplemented: same TTL/FIFO semantics the OSM providers
# already rely on.
from services.providers.osm_common import TtlCache

logger = logging.getLogger("leadmaster.providers.mappls")

TOKEN_URL = "https://outpost.mappls.com/api/security/oauth/token"
TEXT_SEARCH_URL = "https://atlas.mappls.com/api/places/textsearch/json"
AUTOCOMPLETE_URL = "https://atlas.mappls.com/api/places/search/json"
NEARBY_URL = "https://atlas.mappls.com/api/places/nearby/json"
GEOCODE_URL = "https://atlas.mappls.com/api/places/geocode"
REVERSE_GEOCODE_URL = "https://apis.mappls.com/advancedmaps/v1/rev_geocode"

# Place Detail. `/api/places/details/json` answers 404 on this account; the O2O
# entity endpoint is the one that responds, and it takes the eLoc in the path.
PLACE_DETAIL_URL = "https://explore.mappls.com/apis/O2O/entity"

# The advancedmaps family takes the bearer token as a *path* segment rather than
# a header, which is why these are templates rather than plain URLs.
DISTANCE_MATRIX_URL = "https://apis.mappls.com/advancedmaps/v1/{token}/distance_matrix/driving/{coords}"
ROUTE_URL = "https://apis.mappls.com/advancedmaps/v1/{token}/route_adv/driving/{coords}"
SNAP_TO_ROAD_URL = "https://apis.mappls.com/advancedmaps/v1/{token}/snapToRoad"

# Text Search returns 10 per page and pages cleanly (measured: pages 1-3 held
# distinct businesses). Capped so a large `max_results` cannot turn one search
# into an unbounded run of requests.
TEXT_SEARCH_PAGE_SIZE = 10
MAX_TEXT_SEARCH_PAGES = 5

# Place Detail and Geocode responses are stable for a given key, so repeating
# them inside a search — or across searches minutes apart — is wasted quota.
_DETAIL_CACHE = TtlCache()
_GEOCODE_CACHE = TtlCache()

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

    # --- Text Search ----------------------------------------------------

    async def text_search_page(
        self, query: str, location: str | None = None, page: int = 1, item_count: int = TEXT_SEARCH_PAGE_SIZE
    ) -> tuple[list[dict], int]:
        """One page of Text Search. Returns (results, latency_ms).

        `location` is a "lat,lng" reference point that biases results towards an
        area. It is optional because this account cannot produce coordinates for
        a place name — when we have no reference point Mappls still answers, just
        without the proximity bias.
        """
        params: dict = {"query": query, "region": "IND", "itemCount": item_count, "page": page}
        if location:
            params["location"] = location
        payload, latency_ms = await self.get(TEXT_SEARCH_URL, params)
        results = payload.get("suggestedLocations") or payload.get("results") or []
        return results, latency_ms

    # --- Place Detail ---------------------------------------------------

    async def place_detail(self, eloc: str) -> dict | None:
        """Details for one eLoc, cached so a place is never fetched twice.

        Measured against this account, the response carries only `name`,
        `address` and `eloc` — everything Text Search already returned. The
        caller decides whether it is worth a request; this method just makes the
        call correct and cheap when it is made.
        """
        if not eloc:
            return None

        cached = _DETAIL_CACHE.get(eloc)
        if cached is not None:
            return cached

        payload, _ = await self.get(f"{PLACE_DETAIL_URL}/{eloc}", {})
        if isinstance(payload, dict) and payload:
            _DETAIL_CACHE.put(eloc, payload)
            return payload
        return None

    # --- Routing / distance --------------------------------------------

    async def distance_matrix(
        self, origin: tuple[float, float], destinations: list[tuple[float, float]]
    ) -> dict | None:
        """Road distances and durations from one origin to several destinations.

        Coordinates are `lng,lat` in the path — the opposite order to the
        `lat,lng` these arguments take, which is the kind of mismatch that
        silently returns distances for the wrong hemisphere.
        """
        if not destinations:
            return None
        points = [origin, *destinations]
        coords = ";".join(f"{lng},{lat}" for lat, lng in points)
        token = await self.token()
        payload, _ = await self.get(
            DISTANCE_MATRIX_URL.format(token=token, coords=coords), {}
        )
        return payload

    async def route(self, origin: tuple[float, float], destination: tuple[float, float]) -> dict | None:
        """Driving route between two points. Called only on explicit request."""
        coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        token = await self.token()
        payload, _ = await self.get(ROUTE_URL.format(token=token, coords=coords), {})
        return payload

    async def snap_to_road(self, points: list[tuple[float, float]]) -> dict | None:
        """Snaps a GPS trace to the road network.

        Not part of lead search — a business address is not a trace. Exposed for
        callers that genuinely have a path to align.
        """
        if not points:
            return None
        token = await self.token()
        pts = ";".join(f"{lat},{lng}" for lat, lng in points)
        payload, _ = await self.get(SNAP_TO_ROAD_URL.format(token=token), {"pts": pts})
        return payload

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

        wanted = max(1, query.max_results)
        pages_needed = min(
            MAX_TEXT_SEARCH_PAGES,
            -(-wanted // TEXT_SEARCH_PAGE_SIZE),  # ceil
        )

        suggestions: list[dict] = []
        seen_elocs: set[str] = set()
        latency_ms = 0

        # Resolve the search location to a reference point.
        #
        # Mappls Text Search matches on business *name*, not area: "electrical
        # panel manufacturer in Bhopal" returns firms in Kerala and Haryana whose
        # names happen to match. Its Nearby API does scope to an area, but needs
        # a lat/lng — which this account's Geocode cannot supply, since it returns
        # addresses without coordinates.
        #
        # Nominatim fills that one gap. It is already a dependency (Overpass uses
        # it the same way), needs no key, and is asked for exactly one coordinate
        # per search. With a reference point, Nearby becomes usable and Text
        # Search starts returning a real `distance` per result.
        reference = await self._reference_point(query.location)

        # Step 1 — Text Search, paginated.
        #
        # The previous implementation took page 1 only and returned whatever fit,
        # which capped a Mappls search at a handful of leads no matter what was
        # asked for. Pages are fetched one at a time and stop as soon as enough
        # usable results exist or a page comes back short, so a narrow query does
        # not pay for pages it does not need.
        # Step 1a — Nearby, when we have a reference point.
        #
        # This is what makes "in Bhopal" mean Bhopal. Nearby is area-scoped and
        # returns `distance` from the reference point for free, so no Distance
        # Matrix call is needed for these results.
        page = 0
        if reference is not None:
            radius_m = int(min(max((query.radius_km or 25.0), 1.0), 100.0) * 1000)
            try:
                nearby = await self._client.nearby(
                    reference[0], reference[1], radius_m, query.query
                )
                for item in nearby:
                    eloc = item.get("eLoc")
                    if eloc and eloc in seen_elocs:
                        continue
                    if eloc:
                        seen_elocs.add(eloc)
                    item["_source_api"] = "nearby"
                    suggestions.append(item)
            except (PermanentProviderError, TransientProviderError) as exc:
                # A failed Nearby degrades the search to keyword-only; it does
                # not fail it.
                logger.warning("Mappls nearby failed near %s: %s", reference, exc)

        for page in range(1, pages_needed + 1):
            try:
                results, page_latency = await self._client.text_search_page(
                    query.full_text,
                    location=f"{reference[0]},{reference[1]}" if reference else None,
                    page=page,
                )
            except PermanentProviderError as exc:
                if page == 1:
                    logger.warning("Mappls text search rejected: %s", exc)
                    return failed(self.name, str(exc))
                # Later pages failing is a partial result, not a failed search.
                logger.warning("Mappls text search page %s rejected: %s", page, exc)
                break
            except TransientProviderError as exc:
                if page == 1:
                    logger.warning("Mappls text search temporarily unavailable: %s", exc)
                    return failed(self.name, f"Temporarily unavailable: {exc}")
                logger.warning("Mappls text search page %s unavailable: %s", page, exc)
                break

            latency_ms += page_latency
            fresh = [r for r in results if (eloc := r.get("eLoc")) is None or eloc not in seen_elocs]
            for item in fresh:
                if item.get("eLoc"):
                    seen_elocs.add(item["eLoc"])
            suggestions.extend(fresh)

            if len(results) < TEXT_SEARCH_PAGE_SIZE:
                break  # Mappls has nothing more to give.
            if sum(1 for s in suggestions if self._is_business(s)) >= wanted:
                break

        leads = [
            lead
            for item in suggestions
            if (lead := self._to_lead(item, query)) is not None
        ]
        leads = leads[:wanted]

        # Steps 2 and 3 — enrichment, strictly gap-driven. Both are allowed to
        # fail without failing the search.
        detail_failures = await self._fill_gaps_from_place_detail(leads)
        geocode_failures = await self._fill_address_components(leads)

        logger.info(
            "Mappls: %s suggestion(s) over %s page(s) for %r -> %s lead(s) (%sms)"
            "%s%s",
            len(suggestions),
            page,
            query.full_text,
            len(leads),
            latency_ms,
            f", {detail_failures} place-detail failure(s)" if detail_failures else "",
            f", {geocode_failures} geocode failure(s)" if geocode_failures else "",
        )
        self._warn_if_no_coordinates(leads)

        return ProviderSearchResult(
            provider_name=self.name,
            status=ProviderRunStatus.COMPLETED,
            leads=leads,
            latency_ms=latency_ms,
        )

    async def _reference_point(self, location: str | None) -> tuple[float, float] | None:
        """Coordinates for the searched place, or None.

        Uses Nominatim because Mappls cannot answer it on this account: Geocode
        returns an address breakdown with no lat/lng. Exactly one lookup per
        search, and Nominatim's own cache absorbs repeats.

        Returning None is a normal outcome, not an error — the search then falls
        back to keyword-only Text Search, which is what it did before.
        """
        if not location or not location.strip():
            return None
        try:
            from services.providers.openstreetmap import NominatimClient

            geocoder = NominatimClient()
            # Nominatim's policy requires an identifying User-Agent and it
            # rejects requests without one, so an unconfigured geocoder cannot
            # help. Checking first also keeps this out of the network entirely
            # when OSM is not set up — which is what makes a Mappls unit test
            # that stubs only Mappls stay hermetic instead of reaching out to
            # nominatim.openstreetmap.org and serialising on its rate limiter.
            if not geocoder.is_configured:
                return None

            centre = await geocoder.geocode(location.strip())
        except Exception as exc:  # noqa: BLE001 - never fail a search over this
            logger.warning("Could not resolve %r to a reference point: %s", location, exc)
            return None
        if not centre:
            return None
        lat, lng = centre.get("lat"), centre.get("lng")
        if lat is None or lng is None:
            return None
        return float(lat), float(lng)

    @staticmethod
    def _is_business(item: dict) -> bool:
        """Whether a suggestion is a company rather than a place name."""
        return (item.get("type") or "").upper() not in _ADMINISTRATIVE_TYPES

    async def _fill_gaps_from_place_detail(self, leads: list[NormalizedLead]) -> int:
        """Place Detail, but only for leads Text Search left incomplete.

        Measured on this account, Place Detail returns `{name, address, eloc}` —
        nothing Text Search does not already carry. Calling it for every result
        would therefore spend one request per lead to learn nothing, which is
        exactly the quota waste to avoid. It is still worth calling for the
        minority of results that came back without an address, where it can
        genuinely add one.
        """
        failures = 0
        for lead in leads:
            if lead.address:
                continue
            eloc = (lead.raw or {}).get("eloc")
            if not eloc:
                continue
            try:
                detail = await self._client.place_detail(eloc)
            except (PermanentProviderError, TransientProviderError) as exc:
                failures += 1
                logger.warning("Mappls place detail failed for %s: %s", eloc, exc)
                lead.raw["place_detail_error"] = str(exc)[:200]
                continue
            if not detail:
                continue
            address = detail.get("address")
            if address and not lead.address:
                lead.address = address
                lead.raw["source_api"] = _append_api(lead.raw.get("source_api"), "place_detail")
        return failures

    async def _fill_address_components(self, leads: list[NormalizedLead]) -> int:
        """Geocode, used for address components rather than coordinates.

        This account's Geocode returns a full administrative breakdown — locality,
        district, city, state, pincode, eLoc, confidence — but **no latitude or
        longitude**. So it cannot satisfy "geocode to get coordinates"; leaving
        them null is the honest outcome rather than inventing a position.

        It is called only when the lead still lacks a city or pincode after Text
        Search, and the response is cached per address so repeated searches over
        the same area do not re-ask.
        """
        failures = 0
        for lead in leads:
            has_city = bool(lead.city)
            has_pincode = bool((lead.raw or {}).get("pincode"))
            if (has_city and has_pincode) or not lead.address:
                continue

            cache_key = lead.address.strip().lower()
            cached = _GEOCODE_CACHE.get(cache_key)
            if cached is None:
                try:
                    cached = await self._client.geocode(lead.address)
                except (PermanentProviderError, TransientProviderError) as exc:
                    failures += 1
                    logger.warning("Mappls geocode failed for %r: %s", lead.address[:60], exc)
                    lead.raw["geocode_error"] = str(exc)[:200]
                    continue
                if cached is not None:
                    _GEOCODE_CACHE.put(cache_key, cached)
            if not cached:
                continue

            lead.city = lead.city or cached.get("city") or cached.get("district")
            lead.raw["state"] = lead.raw.get("state") or cached.get("state")
            lead.raw["pincode"] = lead.raw.get("pincode") or cached.get("pincode")
            lead.raw["formatted_address"] = cached.get("formattedAddress")
            lead.raw["geocode_level"] = cached.get("geocodeLevel")
            lead.raw["source_api"] = _append_api(lead.raw.get("source_api"), "geocode")
            # Coordinates are deliberately not read here: this account returns
            # none, and a fabricated position is worse than an absent one.
        return failures

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

        eloc = item.get("eLoc")
        keywords = item.get("keywords") or []

        return NormalizedLead(
            company_name=name,
            # Mappls classifies POIs with keyword codes (SHPIND, HLTHSP, FODCOF).
            # The code is the only category signal it gives, so it is recorded
            # verbatim rather than guessed at — an expanded label we invented
            # would be a fabricated field.
            industry=query.industry or (keywords[0] if keywords else None),
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
                # Mappls' own stable identifier. The strongest dedup key this
                # provider offers, and what the detail/route calls take.
                "eloc": eloc,
                "place_id": eloc,
                "mappls_url": f"https://maps.mappls.com/{eloc}" if eloc else None,
                "address": address,
                "state": state,
                "pincode": pincode,
                "mappls_type": item.get("type"),
                "mappls_keywords": keywords,
                # Distance is only present on Nearby responses, where it is
                # measured from the reference point the caller supplied.
                "distance_meters": _as_int(item.get("distance")),
                "source_api": item.get("_source_api") or "text_search",
                "search_keyword": query.query,
                "search_location": query.location,
                "retrieved_at": datetime.now(UTC).isoformat(),
            },
            source_provider=self.name,
        )


def _append_api(existing: str | None, api: str) -> str:
    """Tracks which Mappls APIs contributed to a lead, in call order."""
    if not existing:
        return api
    parts = existing.split("+")
    if api in parts:
        return existing
    return "+".join([*parts, api])


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
