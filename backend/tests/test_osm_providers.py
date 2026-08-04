"""OpenStreetMap (Nominatim) and Overpass providers.

Outbound HTTP is intercepted: these are donated public services, and a test
suite that hammers them on every run is exactly the abuse their usage policies
exist to prevent. What is exercised for real is everything we own — the Overpass
QL generator, keyword/radius handling, tag extraction, the rate limiter, the
cache, and graceful degradation. Both were verified against the live APIs
separately (see docs/PROVIDERS.md).
"""

import asyncio
import time

import httpx
import pytest

from services.providers import openstreetmap, osm_common, overpass
from services.providers.base import ProviderRunStatus, SearchQuery

asyncio_test = pytest.mark.asyncio(loop_scope="session")


# Captured from the live APIs.
NOMINATIM_CITY = [
    {
        "place_id": 247875552,
        "osm_type": "node",
        "osm_id": 245711197,
        "lat": "23.0215374",
        "lon": "72.5800568",
        "display_name": "Ahmedabad, Gujarat, 380001, India",
        "name": "Ahmedabad",
        "category": "place",
        "type": "city",
        "address": {"city": "Ahmedabad", "state": "Gujarat", "postcode": "380001", "country": "India"},
        "licence": "Data (c) OpenStreetMap contributors, ODbL 1.0",
    }
]

NOMINATIM_POI = [
    {
        "place_id": 248856541,
        "osm_type": "way",
        "osm_id": 85209894,
        "lat": "23.0263605",
        "lon": "72.5721733",
        "name": "Patang - The Revolving Restaurant",
        "display_name": "Patang - The Revolving Restaurant, Nehru Bridge, Paldi, Ahmedabad, Gujarat, 380009, India",
        "category": "amenity",
        "type": "restaurant",
        "address": {
            "road": "Nehru Bridge",
            "suburb": "Paldi",
            "state_district": "Ahmedabad",
            "state": "Gujarat",
            "postcode": "380009",
            "country": "India",
        },
        "extratags": {
            "website": "http://www.neelkanthpatang.com/",
            "opening_hours": "Mo-Su 12:00-15:00,19:00-23:30",
            "cuisine": "multicuisine",
            "phone": "+91 79 2657 1234",
        },
        "licence": "Data (c) OpenStreetMap contributors, ODbL 1.0",
    },
    # Unnamed element: geography, not a business.
    {"place_id": 1, "osm_type": "way", "osm_id": 2, "lat": "23.1", "lon": "72.6", "display_name": ""},
]

OVERPASS_ELEMENTS = {
    "elements": [
        {
            "type": "node",
            "id": 440305869,
            "lat": 23.0085819,
            "lon": 72.5432503,
            "tags": {
                "amenity": "hospital",
                "name": "Jivraj Mehta Hospital",
                "addr:street": "Dr Jivraj Mehta Marg",
                "addr:housenumber": "12",
                "addr:suburb": "Vasna",
                "addr:city": "Ahmedabad",
                "addr:state": "Gujarat",
                "addr:postcode": "380007",
                "addr:country": "IN",
                "phone": "+91 79 2666 1234",
                "contact:mobile": "+91 98250 11111",
                "website": "https://jivrajmehta.example.org",
                "contact:email": "info@jivrajmehta.example.org",
                "contact:facebook": "https://facebook.com/jivrajmehta",
                "contact:instagram": "@jivrajmehta",
                "contact:linkedin": "https://linkedin.com/company/jivrajmehta",
                "opening_hours": "24/7",
                "operator": "Jivraj Mehta Trust",
                "brand": "Jivraj Mehta",
                "wheelchair": "yes",
                "healthcare:speciality": "general",
                "payment:cash": "yes",
                "payment:visa": "yes",
                "payment:bitcoin": "no",
            },
        },
        {
            # A way: coordinates live under `center`, not lat/lon.
            "type": "way",
            "id": 973444844,
            "center": {"lat": 23.0306, "lon": 72.2964227},
            "tags": {"amenity": "hospital", "name": "Way Hospital"},
        },
        # Unnamed way — a building outline, not a lead.
        {"type": "way", "id": 999, "center": {"lat": 23.0, "lon": 72.5}, "tags": {"building": "yes"}},
    ]
}


def _query(**kwargs) -> SearchQuery:
    return SearchQuery(**{"query": "hospital", "location": "Ahmedabad", "max_results": 5, **kwargs})


class _Recorder:
    def __init__(self, routes):
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        for fragment, payload in self.routes.items():
            if fragment in str(request.url):
                if isinstance(payload, int):
                    return httpx.Response(payload, text="<html>Overpass error</html>")
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"error": f"unrouted {request.url}"})


def _intercept(monkeypatch, routes) -> _Recorder:
    """Replaces `request_json` in both OSM modules with a mock-transport version."""
    recorder = _Recorder(routes)

    async def request_json(method, url, *, params=None, json_body=None, form_body=None,
                           headers=None, timeout=None):
        async with httpx.AsyncClient(transport=httpx.MockTransport(recorder), timeout=5) as client:
            response = await client.request(
                method, url, params=params, json=json_body, data=form_body, headers=headers or {}
            )
        if response.status_code == 429 or response.status_code >= 500:
            from services.providers.http import TransientProviderError

            raise TransientProviderError(f"status {response.status_code}")
        if response.status_code >= 400:
            from services.providers.http import PermanentProviderError

            raise PermanentProviderError(f"status {response.status_code}: {response.text[:80]}")
        return response.json(), 12

    monkeypatch.setattr(openstreetmap, "request_json", request_json)
    monkeypatch.setattr(overpass, "request_json", request_json)
    return recorder


@pytest.fixture(autouse=True)
def _isolate_osm_state(monkeypatch):
    """Per-test OSM state: configured endpoints, empty caches, no rate delay.

    `conftest` blanks OSM_USER_AGENT and OVERPASS_URL so the *rest* of the suite
    can never call these donated services. This module is about them, so it puts
    the values back — every outbound request here is intercepted by `_intercept`.

    The caches are process-wide and would leak between tests. The Nominatim rate
    limiter is neutralized because nothing here touches the network; it has its
    own dedicated test below.
    """
    monkeypatch.setattr(openstreetmap.settings, "OSM_USER_AGENT", "LeadMasterAI/1.0", raising=False)
    monkeypatch.setattr(
        overpass.settings, "OVERPASS_URL", "https://overpass.test/api/interpreter", raising=False
    )

    original_interval = osm_common.nominatim_limiter.min_interval
    osm_common.nominatim_limiter.min_interval = 0.0
    osm_common.nominatim_cache.clear()
    osm_common.overpass_cache.clear()
    yield
    osm_common.nominatim_limiter.min_interval = original_interval
    osm_common.nominatim_cache.clear()
    osm_common.overpass_cache.clear()


# --- Politeness: User-Agent, rate limit, cache ----------------------------


@asyncio_test
async def test_nominatim_sends_the_required_user_agent(monkeypatch):
    """Nominatim rejects requests without an identifying User-Agent."""
    monkeypatch.setattr(openstreetmap.settings, "OSM_USER_AGENT", "LeadMasterAI/1.0", raising=False)
    recorder = _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY})

    await openstreetmap.NominatimClient().geocode("Ahmedabad")

    assert recorder.requests[0].headers["User-Agent"] == "LeadMasterAI/1.0"


@asyncio_test
async def test_identical_nominatim_queries_are_served_from_cache(monkeypatch):
    """Repeating a question to a donated service is the thing to avoid."""
    recorder = _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY})
    client = openstreetmap.NominatimClient()

    first = await client.geocode("Ahmedabad")
    second = await client.geocode("Ahmedabad")

    assert first == second
    assert len(recorder.requests) == 1, "the second call must not hit the network"


@asyncio_test
async def test_rate_limiter_enforces_a_minimum_gap():
    """Nominatim's policy is 1 request/second; the limiter is process-wide."""
    limiter = osm_common.RateLimiter(min_interval=0.25)
    started = time.monotonic()
    await asyncio.gather(*(limiter.acquire() for _ in range(3)))
    elapsed = time.monotonic() - started

    # Three acquisitions => at least two gaps.
    assert elapsed >= 0.5


def test_ttl_cache_expires_entries():
    cache = osm_common.TtlCache(ttl=0.05)
    cache.put("k", "v")
    assert cache.get("k") == "v"
    time.sleep(0.08)
    assert cache.get("k") is None


def test_ttl_cache_evicts_when_full():
    cache = osm_common.TtlCache(max_entries=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    # Oldest insertion is dropped, not the most recent.
    assert cache.get("a") is None
    assert cache.get("c") == 3


# --- Geocoding ------------------------------------------------------------


@asyncio_test
async def test_forward_geocoding_coerces_string_coordinates(monkeypatch):
    """Nominatim returns lat/lon as strings; callers need floats."""
    _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY})

    result = await openstreetmap.NominatimClient().geocode("Ahmedabad, Gujarat, India")

    assert result == {
        "lat": 23.0215374,
        "lng": 72.5800568,
        "formatted_address": "Ahmedabad, Gujarat, 380001, India",
    }
    assert isinstance(result["lat"], float)


@asyncio_test
async def test_reverse_geocoding(monkeypatch):
    payload = {
        "lat": "23.0224986",
        "lon": "72.5714409",
        "display_name": "Ashram Road, Navrangpura, Ahmedabad, Gujarat, 380006, India",
    }
    _intercept(monkeypatch, {"reverse": payload})

    result = await openstreetmap.NominatimClient().reverse_geocode(23.0225, 72.5714)
    assert result["formatted_address"].startswith("Ashram Road")
    assert result["lat"] == 23.0224986


@asyncio_test
async def test_geocoding_no_match_returns_none(monkeypatch):
    _intercept(monkeypatch, {"nominatim": []})
    assert await openstreetmap.NominatimClient().geocode("Xyzzyville") is None


# --- OpenStreetMap lead provider -----------------------------------------


@asyncio_test
async def test_osm_provider_needs_no_credentials(monkeypatch):
    monkeypatch.setattr(openstreetmap.settings, "OSM_USER_AGENT", "LeadMasterAI/1.0", raising=False)
    assert openstreetmap.OpenStreetMapProvider().is_configured is True


@asyncio_test
async def test_osm_search_maps_results_to_leads(monkeypatch):
    _intercept(monkeypatch, {"nominatim": NOMINATIM_POI})

    result = await openstreetmap.OpenStreetMapProvider().search(_query(query="restaurant"))

    assert result.status is ProviderRunStatus.COMPLETED
    # The unnamed element is dropped.
    assert result.count == 1
    lead = result.leads[0]
    assert lead.company_name == "Patang - The Revolving Restaurant"
    assert (lead.lat, lead.lng) == (23.0263605, 72.5721733)
    assert lead.website == "http://www.neelkanthpatang.com/"
    assert lead.phone == "+91 79 2657 1234"
    assert lead.city == "Ahmedabad"
    assert lead.country == "India"
    assert lead.raw["osm_element"] == "way/85209894"
    assert lead.raw["place_id"] == 248856541
    assert lead.raw["opening_hours"] == "Mo-Su 12:00-15:00,19:00-23:30"
    # ODbL attribution travels with the lead.
    assert "OpenStreetMap" in lead.raw["licence"]


# --- Overpass QL generation ----------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected_terms"),
    [
        ("restaurant", ["restaurant"]),
        ("solar, wind, EV", ["solar, wind, EV", "solar", "wind", "EV"]),
        ("solar and wind", ["solar and wind", "solar", "wind"]),
        ("solar | wind", ["solar | wind", "solar", "wind"]),
        ("Industrial Automation", ["Industrial Automation"]),
    ],
)
def test_multi_keyword_splitting(text, expected_terms):
    assert overpass.split_keywords(text) == expected_terms


@pytest.mark.parametrize(
    ("keyword", "fragment"),
    [
        ("restaurant", '["amenity"="restaurant"]'),
        ("hospital", '["amenity"="hospital"]'),
        ("factory", '["man_made"="works"]'),
        ("manufacturer", '["man_made"="works"]'),
        ("solar", '["generator:source"="solar"]'),
        ("wind", '["generator:source"="wind"]'),
        ("EV", '["amenity"="charging_station"]'),
        ("electrical", '["craft"="electrician"]'),
        ("car dealer", '["shop"="car"]'),
    ],
)
def test_keyword_maps_to_osm_tags(keyword, fragment):
    assert fragment in overpass.selectors_for(keyword)


@pytest.mark.parametrize("keyword", ["PLC", "SCADA", "Panel Builder"])
def test_keywords_osm_has_no_tag_for_fall_back_to_name_regex(keyword):
    """These are not OSM tags and never will be; a name match is the only route."""
    assert overpass.selectors_for(keyword) == ()
    ql = overpass.build_query([keyword], 23.0, 72.5, 10, 5)
    assert f'["name"~"{keyword}",i]' in ql


def test_tagged_keywords_do_not_also_add_a_name_regex():
    """Measured: tag+regex for one keyword was throttled (429) and returned nothing.

    Tag-only answered in ~19s. Precision that completes beats recall that is
    rejected, so a keyword with tags uses tags alone.
    """
    ql = overpass.build_query(["hospital"], 23.0, 72.5, 10, 5)
    assert '["amenity"="hospital"]' in ql
    assert '"name"~' not in ql


def test_query_covers_node_way_and_relation():
    """Ways and relations matter: industrial premises are rarely nodes."""
    ql = overpass.build_query(["hospital"], 23.0, 72.5, 10, 5)
    for element in ("node", "way", "relation"):
        assert f'{element}["amenity"="hospital"]' in ql


def test_query_requests_center_so_ways_have_coordinates():
    """Without `out center`, ways and relations come back with no position."""
    ql = overpass.build_query(["hospital"], 23.0, 72.5, 10, 5)
    assert "out center tags 5;" in ql


def test_around_filter_uses_radius_lat_lon_order():
    """Overpass wants radius,lat,lon — not the lon-first GeoJSON order."""
    ql = overpass.build_query(["hospital"], 23.0225, 72.5714, 15, 5)
    assert "(around:15000,23.0225,72.5714)" in ql


@pytest.mark.parametrize(
    ("given", "expected"),
    [(None, 25), (0, 1), (0.5, 1), (1, 1), (50, 50), (100, 100), (500, 100), ("abc", 25)],
)
def test_radius_is_clamped_to_the_supported_band(given, expected):
    assert overpass.clamp_radius_km(given) == expected


def test_a_quote_in_a_keyword_cannot_break_out_of_the_regex():
    """The keyword is embedded in a double-quoted Overpass regex."""
    ql = overpass.build_query(['bad"keyword'], 23.0, 72.5, 10, 5)
    # The quote is stripped, so the QL string stays well-formed.
    assert '~"badkeyword",i' in ql
    assert '~"bad"keyword"' not in ql


def test_multiple_keywords_produce_one_unioned_query():
    """One request per search — issuing one per tag is what triggered 429s."""
    ql = overpass.build_query(["hospital", "restaurant", "PLC"], 23.0, 72.5, 10, 5)
    assert ql.count("[out:json]") == 1
    assert '["amenity"="hospital"]' in ql
    assert '["amenity"="restaurant"]' in ql
    assert '["name"~"PLC",i]' in ql


# --- Overpass provider ---------------------------------------------------


@asyncio_test
async def test_overpass_extracts_every_public_field(monkeypatch):
    _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY, "interpreter": OVERPASS_ELEMENTS})

    result = await overpass.OverpassProvider().search(_query(max_results=10, radius_km=15))

    assert result.status is ProviderRunStatus.COMPLETED
    # Two named elements; the unnamed building is dropped.
    assert result.count == 2

    lead = result.leads[0]
    assert lead.company_name == "Jivraj Mehta Hospital"
    assert (lead.lat, lead.lng) == (23.0085819, 72.5432503)
    assert lead.phone == "+91 79 2666 1234"
    assert lead.email == "info@jivrajmehta.example.org"
    assert lead.website == "https://jivrajmehta.example.org"
    assert lead.city == "Ahmedabad"
    assert lead.address == "12 Dr Jivraj Mehta Marg, Vasna, Ahmedabad, Gujarat, 380007"

    raw = lead.raw
    assert raw["osm_element"] == "node/440305869"
    assert raw["category"] == "Hospital"
    assert raw["subcategory"] == "General"
    assert raw["street"] == "Dr Jivraj Mehta Marg"
    assert raw["area"] == "Vasna"
    assert raw["state"] == "Gujarat"
    assert raw["postal_code"] == "380007"
    assert raw["mobile"] == "+91 98250 11111"
    assert raw["opening_hours"] == "24/7"
    assert raw["operator"] == "Jivraj Mehta Trust"
    assert raw["brand"] == "Jivraj Mehta"
    assert raw["wheelchair"] == "yes"
    # payment:bitcoin=no must not be listed as accepted.
    assert raw["payment_methods"] == ["cash", "visa"]
    assert raw["social"]["facebook"] == "https://facebook.com/jivrajmehta"
    assert raw["social"]["instagram"] == "@jivrajmehta"
    assert raw["social"]["linkedin"] == "https://linkedin.com/company/jivrajmehta"


@asyncio_test
async def test_way_coordinates_come_from_center(monkeypatch):
    """Ways carry no lat/lon of their own — only `center`, and only if asked."""
    _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY, "interpreter": OVERPASS_ELEMENTS})

    result = await overpass.OverpassProvider().search(_query(max_results=10))
    way_lead = next(l for l in result.leads if l.company_name == "Way Hospital")

    assert (way_lead.lat, way_lead.lng) == (23.0306, 72.2964227)


@asyncio_test
async def test_missing_values_stay_none_and_are_never_invented(monkeypatch):
    """The integration spec is explicit: absent fields stay NULL."""
    sparse = {"elements": [{"type": "node", "id": 1, "lat": 23.0, "lon": 72.5,
                            "tags": {"amenity": "hospital", "name": "Bare Clinic"}}]}
    _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY, "interpreter": sparse})

    lead = (await overpass.OverpassProvider().search(_query())).leads[0]

    assert lead.phone is None
    assert lead.email is None
    assert lead.website is None
    assert lead.address is None
    assert lead.raw["opening_hours"] is None
    assert lead.raw["operator"] is None
    assert lead.raw["payment_methods"] is None
    assert lead.raw["social"] is None


@asyncio_test
async def test_overpass_needs_no_credentials(monkeypatch):
    """Configured means "has an endpoint" — there is no key to supply.

    conftest blanks OVERPASS_URL so the rest of the suite never calls the real
    service, so this test restores it to assert the actual contract.
    """
    monkeypatch.setattr(
        overpass.settings, "OVERPASS_URL", "https://overpass-api.de/api/interpreter", raising=False
    )
    assert overpass.OverpassProvider().is_configured is True


@asyncio_test
async def test_identical_overpass_queries_are_cached(monkeypatch):
    recorder = _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY, "interpreter": OVERPASS_ELEMENTS})
    provider = overpass.OverpassProvider()

    await provider.search(_query())
    interpreter_calls = sum(1 for r in recorder.requests if "interpreter" in str(r.url))
    await provider.search(_query())
    after = sum(1 for r in recorder.requests if "interpreter" in str(r.url))

    assert interpreter_calls == 1
    assert after == 1, "the repeated Overpass query must come from cache"


@asyncio_test
async def test_overpass_posts_the_query_as_form_data(monkeypatch):
    recorder = _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY, "interpreter": OVERPASS_ELEMENTS})

    await overpass.OverpassProvider().search(_query())

    request = next(r for r in recorder.requests if "interpreter" in str(r.url))
    assert request.method == "POST"
    body = request.content.decode()
    assert body.startswith("data=")
    assert "out+center+tags" in body or "out center tags" in body


# --- Graceful degradation ------------------------------------------------


@asyncio_test
async def test_throttled_overpass_fails_softly(monkeypatch):
    """429 after retries must not fail the whole search — other providers continue."""
    _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY, "interpreter": 429})

    result = await overpass.OverpassProvider().search(_query())

    assert result.status is ProviderRunStatus.FAILED
    assert result.leads == []
    assert "throttled or busy" in result.error


@asyncio_test
async def test_overloaded_overpass_fails_softly(monkeypatch):
    """504 is Overpass's usual overload reply, and its body is HTML not JSON."""
    _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY, "interpreter": 504})

    result = await overpass.OverpassProvider().search(_query())
    assert result.status is ProviderRunStatus.FAILED
    assert result.leads == []


@asyncio_test
async def test_unresolvable_location_fails_without_querying_overpass(monkeypatch):
    recorder = _intercept(monkeypatch, {"nominatim": [], "interpreter": OVERPASS_ELEMENTS})

    result = await overpass.OverpassProvider().search(_query(location="Xyzzyville"))

    assert result.status is ProviderRunStatus.FAILED
    assert "could not locate" in result.error
    assert not any("interpreter" in str(r.url) for r in recorder.requests)


@asyncio_test
async def test_missing_location_is_skipped(monkeypatch):
    recorder = _intercept(monkeypatch, {"nominatim": NOMINATIM_CITY})
    result = await overpass.OverpassProvider().search(SearchQuery(query="hospital"))

    assert result.status is ProviderRunStatus.SKIPPED
    assert "location is required" in result.error
    assert recorder.requests == []


# --- Registry / catalogue wiring -----------------------------------------


def test_both_providers_are_registered_lead_sources():
    from services.providers import registry

    assert "OpenStreetMap" in registry.LEAD_SOURCE_NAMES
    assert "Overpass API" in registry.LEAD_SOURCE_NAMES


def test_neither_provider_asks_for_credentials():
    """Absence from the spec map is what makes the API Manager say "no key required"."""
    from services.providers import registry

    assert "OpenStreetMap" not in registry.PROVIDER_CREDENTIAL_SPECS
    assert "Overpass API" not in registry.PROVIDER_CREDENTIAL_SPECS


def test_seed_catalogue_lists_both_with_icons():
    from scripts.seed_data import PROVIDERS

    by_name = {row[0]: row for row in PROVIDERS}
    for name in ("OpenStreetMap", "Overpass API"):
        assert name in by_name, f"{name} missing from the seeded catalogue"
        _n, _category, logo, description, _limit, _cost = by_name[name]
        assert logo, "a provider needs an icon for the API Manager grid"
        assert "no api key" in description.lower()


# --- Existing providers must be untouched --------------------------------


def test_existing_providers_still_registered():
    """This change adds providers; it must not remove or rename any."""
    from services.providers import registry

    for name in (
        "Google Places",
        "Mappls (MapmyIndia)",
        "Bing Search",
        "Geoapify",
        "Company Website Search",
    ):
        assert name in registry.LEAD_SOURCE_NAMES

    for name in ("Google Places", "Mappls (MapmyIndia)", "Bing Search", "Geoapify"):
        assert name in registry.PROVIDER_CREDENTIAL_SPECS
