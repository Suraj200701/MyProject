"""Geoapify provider: keyword->category mapping, the two-step search, parsing.

Outbound HTTP is intercepted — a test suite must not depend on a third-party
quota. What is exercised for real is everything we own: the category taxonomy,
the geocode-then-circle sequence, GeoJSON parsing, and the maps_service provider
chain. The live API was verified separately (see docs/API_TESTING.md).
"""

import httpx
import pytest

from services import maps_service
from services.providers import geoapify
from services.providers.base import ProviderRunStatus, SearchQuery

asyncio_test = pytest.mark.asyncio(loop_scope="session")


def _query(**kwargs) -> SearchQuery:
    defaults = {"query": "dentists", "location": "Ahmedabad", "max_results": 5}
    return SearchQuery(**{**defaults, "location": defaults["location"], **kwargs})


# Shapes captured from the live API.
GEOCODE_RESPONSE = {
    "features": [
        {
            "properties": {
                "lat": 23.0215374,
                "lon": 72.5800568,
                "formatted": "Ahmedabad, GJ, India",
                "result_type": "city",
            }
        }
    ]
}

PLACES_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "properties": {
                "name": "Premal Dental Clinic",
                "formatted": "Premal Dental Clinic, Punit Marg, Maninagar, - 380008, Gujarat, India",
                "address_line1": "Premal Dental Clinic",
                "street": "Punit Marg",
                "suburb": "Maninagar",
                "state_district": "Ahmedabad",
                "state": "Gujarat",
                "postcode": "380008",
                "country": "India",
                "lat": 23.0029601,
                "lon": 72.6075452,
                "categories": ["healthcare", "healthcare.dentist"],
                "place_id": "51e0354305e22652405961b1",
                "website": "https://premaldental.example.com",
                "phone": "+91 79 1234 5678",
                "opening_hours": "Mo-Sa 09:00-19:00",
                "datasource": {"sourcename": "openstreetmap"},
            },
            "geometry": {"type": "Point", "coordinates": [72.6075452, 23.0029601]},
        },
        {
            # No name and no address_line1 — not a lead.
            "properties": {"lat": 23.1, "lon": 72.6, "categories": ["building"]},
        },
    ],
}


class _Recorder:
    """Captures each outbound request and replies from a URL->payload map."""

    def __init__(self, routes: dict[str, dict]):
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        for fragment, payload in self.routes.items():
            if fragment in str(request.url):
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"error": f"no route for {request.url}"})

    def url_containing(self, fragment: str) -> httpx.URL:
        for request in self.requests:
            if fragment in str(request.url):
                return request.url
        raise AssertionError(f"no request matched {fragment!r}: {[str(r.url) for r in self.requests]}")


def _intercept(monkeypatch, routes: dict[str, dict]) -> _Recorder:
    """Routes provider HTTP through a MockTransport, scoped to this module."""
    recorder = _Recorder(routes)
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(recorder)
        return real_client(*args, **kwargs)

    # `request_json` in providers.http builds the client, so patch it there.
    monkeypatch.setattr(geoapify, "request_json", _passthrough_request_json(factory))
    return recorder


def _passthrough_request_json(client_factory):
    """A `request_json` that uses the mocked client but keeps the real contract."""

    async def request_json(method, url, *, params=None, json_body=None, form_body=None,
                           headers=None, timeout=None):
        async with client_factory(timeout=5) as client:
            response = await client.request(
                method, url, params=params, json=json_body, data=form_body, headers=headers or {}
            )
        if response.status_code >= 400:
            from services.providers.http import PermanentProviderError

            raise PermanentProviderError(f"Provider rejected ({response.status_code}): {response.text[:200]}")
        return response.json(), 42

    return request_json


# --- Keyword -> category --------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("dentists", ("healthcare.dentist",)),
        ("dentists in Ahmedabad", ("healthcare.dentist",)),
        ("Restaurants", ("catering.restaurant",)),
        ("real estate", ("office.estate_agent",)),
        ("car dealers", ("commercial.vehicle",)),
        ("manufacturers", ("production",)),
        ("supermarket", ("commercial.supermarket",)),
        # Separators normalized.
        ("car-dealers", ("commercial.vehicle",)),
    ],
)
def test_keyword_maps_to_category(text, expected):
    assert geoapify.categories_for(text) == expected


def test_multi_word_keywords_win_over_their_parts():
    """"dental clinic" must not resolve via the shorter "clinic"."""
    assert geoapify.categories_for("dental clinic") == ("healthcare.dentist",)
    assert geoapify.categories_for("clinic") == ("healthcare.clinic_or_praxis",)


def test_keywords_match_whole_words_only():
    """Substring matching would map "barbecue" to `catering.bar`."""
    assert geoapify.categories_for("barbecue") == ()
    assert geoapify.categories_for("bar") == ("catering.bar", "catering.pub")


def test_industry_participates_in_matching():
    assert geoapify.categories_for("find me some places", industry="hotel") == (
        "accommodation.hotel",
    )


def test_unknown_keyword_yields_no_categories():
    assert geoapify.categories_for("quantum widget forges") == ()


def test_every_shipped_category_code_is_syntactically_plausible():
    """Guards against a typo silently 400ing every search for that keyword.

    Geoapify rejects unknown codes, and the shipped set was verified against the
    live API; this catches a later edit that introduces an obviously wrong shape.
    """
    for codes in geoapify._KEYWORD_CATEGORIES.values():
        assert codes, "a keyword must map to at least one category"
        for code in codes:
            assert code.islower()
            assert " " not in code
            assert not code.startswith(".") and not code.endswith(".")


# --- The two-step search --------------------------------------------------


@asyncio_test
async def test_search_geocodes_then_queries_a_circle(monkeypatch):
    """Places requires a spatial filter, so the location must be geocoded first."""
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_SEARCH_RADIUS_METERS", 20000, raising=False)
    recorder = _intercept(
        monkeypatch, {"geocode/search": GEOCODE_RESPONSE, "/places": PLACES_RESPONSE}
    )

    result = await geoapify.GeoapifyProvider().search(_query())

    assert result.status is ProviderRunStatus.COMPLETED
    # Geocoding lives under /v1 and Places under /v2 — a single base URL would
    # 404 one of them.
    assert "/v1/geocode/search" in str(recorder.url_containing("geocode/search"))
    places_url = recorder.url_containing("/places")
    assert "/v2/places" in str(places_url)
    assert places_url.params["categories"] == "healthcare.dentist"
    # circle is lon,lat,radius — longitude FIRST. Swapping searches the wrong place.
    assert places_url.params["filter"] == "circle:72.5800568,23.0215374,20000"


@asyncio_test
async def test_search_parses_places_into_leads(monkeypatch):
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    _intercept(monkeypatch, {"geocode/search": GEOCODE_RESPONSE, "/places": PLACES_RESPONSE})

    result = await geoapify.GeoapifyProvider().search(_query(industry=None))

    # The nameless feature is dropped.
    assert result.count == 1
    lead = result.leads[0]
    assert lead.company_name == "Premal Dental Clinic"
    # Coordinates are the whole reason this provider exists.
    assert (lead.lat, lead.lng) == (23.0029601, 72.6075452)
    assert lead.address.startswith("Premal Dental Clinic, Punit Marg")
    # `city` is absent on this feature, so it falls through to state_district.
    assert lead.city == "Ahmedabad"
    assert lead.country == "India"
    assert lead.website == "https://premaldental.example.com"
    assert lead.phone == "+91 79 1234 5678"
    # Most specific category becomes a readable industry label.
    assert lead.industry == "Dentist"
    assert lead.raw["postcode"] == "380008"
    assert lead.raw["place_id"] == "51e0354305e22652405961b1"
    assert lead.raw["opening_hours"] == "Mo-Sa 09:00-19:00"


@asyncio_test
async def test_city_falls_back_through_the_admin_hierarchy(monkeypatch):
    """Suburban POIs often have no `city`; leaving it null hides them from filters."""
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    payload = {
        "features": [
            {
                "properties": {
                    "name": "Suburb Cafe",
                    "formatted": "Suburb Cafe, Somewhere",
                    "suburb": "Maninagar",
                    "lat": 23.0,
                    "lon": 72.6,
                    "categories": ["catering.cafe"],
                }
            }
        ]
    }
    _intercept(monkeypatch, {"geocode/search": GEOCODE_RESPONSE, "/places": payload})

    result = await geoapify.GeoapifyProvider().search(_query(query="cafes"))
    assert result.leads[0].city == "Maninagar"


@asyncio_test
async def test_unmapped_keyword_is_skipped_without_calling_out(monkeypatch):
    """A broad `commercial` fallback would return unrelated shops as if they matched."""
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    recorder = _intercept(monkeypatch, {"geocode/search": GEOCODE_RESPONSE, "/places": PLACES_RESPONSE})

    result = await geoapify.GeoapifyProvider().search(_query(query="quantum widget forges"))

    assert result.status is ProviderRunStatus.SKIPPED
    assert "No Geoapify category matches" in result.error
    # Names some supported keywords so the message is actionable.
    assert "restaurants" in result.error
    assert recorder.requests == []


@asyncio_test
async def test_missing_location_is_skipped(monkeypatch):
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    recorder = _intercept(monkeypatch, {"geocode/search": GEOCODE_RESPONSE})

    result = await geoapify.GeoapifyProvider().search(SearchQuery(query="dentists"))

    assert result.status is ProviderRunStatus.SKIPPED
    assert "location is required" in result.error
    assert recorder.requests == []


@asyncio_test
async def test_unresolvable_location_fails_rather_than_returning_nothing(monkeypatch):
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    _intercept(monkeypatch, {"geocode/search": {"features": []}})

    result = await geoapify.GeoapifyProvider().search(_query(location="Xyzzyville"))

    assert result.status is ProviderRunStatus.FAILED
    assert "could not locate" in result.error


@asyncio_test
async def test_unconfigured_provider_is_skipped(monkeypatch):
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "", raising=False)
    result = await geoapify.GeoapifyProvider().search(_query())
    assert result.status is ProviderRunStatus.SKIPPED
    assert "GEOAPIFY_API_KEY" in result.error


@asyncio_test
async def test_max_results_is_honoured(monkeypatch):
    """max_results is the cost ceiling credit metering reserves against."""
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    many = {
        "features": [
            {
                "properties": {
                    "name": f"Clinic {i}",
                    "formatted": f"Clinic {i}, Ahmedabad",
                    "lat": 23.0 + i / 1000,
                    "lon": 72.6,
                    "categories": ["healthcare.dentist"],
                }
            }
            for i in range(10)
        ]
    }
    recorder = _intercept(monkeypatch, {"geocode/search": GEOCODE_RESPONSE, "/places": many})

    result = await geoapify.GeoapifyProvider().search(_query(max_results=3))
    assert result.count == 3
    assert recorder.url_containing("/places").params["limit"] == "3"


# --- Base URL handling ----------------------------------------------------


@pytest.mark.parametrize(
    "configured",
    [
        "https://api.geoapify.com",
        "https://api.geoapify.com/",
        # The value Geoapify's own docs hand out — and the one that breaks a naive
        # implementation, because geocoding lives under /v1.
        "https://api.geoapify.com/v2",
        "https://api.geoapify.com/v2/",
        "https://api.geoapify.com/v1",
    ],
)
def test_origin_strips_any_configured_version_suffix(monkeypatch, configured):
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_BASE_URL", configured, raising=False)
    assert geoapify.settings.geoapify_origin == "https://api.geoapify.com"


# --- maps_service provider chain -----------------------------------------


@asyncio_test
async def test_geoapify_becomes_the_geocoder_when_google_is_absent(monkeypatch):
    """The point of adding it: a deployment with no Google key can still geocode."""
    monkeypatch.setattr(maps_service.settings, "GOOGLE_MAPS_API_KEY", "", raising=False)
    monkeypatch.setattr(maps_service.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    _intercept(monkeypatch, {"geocode/search": GEOCODE_RESPONSE})

    result = await maps_service.geocode_address("Ahmedabad, Gujarat")
    assert result == {
        "lat": 23.0215374,
        "lng": 72.5800568,
        "formatted_address": "Ahmedabad, GJ, India",
    }


@asyncio_test
async def test_no_provider_configured_names_every_option(monkeypatch):
    for attr in ("GOOGLE_MAPS_API_KEY", "GEOAPIFY_API_KEY", "MAPPLS_CLIENT_ID", "MAPPLS_CLIENT_SECRET"):
        monkeypatch.setattr(maps_service.settings, attr, "", raising=False)

    from utils.exceptions import BadRequestError

    with pytest.raises(BadRequestError) as exc:
        await maps_service.geocode_address("anywhere")

    message = str(exc.value.detail)
    assert "GEOAPIFY_API_KEY" in message
    assert "GOOGLE_MAPS_API_KEY" in message
    assert "MAPPLS_CLIENT_ID" in message


# --- Registry wiring -----------------------------------------------------


def test_geoapify_is_a_registered_lead_source():
    from services.providers import registry

    assert "Geoapify" in registry.LEAD_SOURCE_NAMES
    spec = registry.PROVIDER_CREDENTIAL_SPECS["Geoapify"]
    assert spec.key_env_var == "GEOAPIFY_API_KEY"
    # Single key, not a pair.
    assert spec.secret_label is None


# --- Provider routing regression -----------------------------------------


@asyncio_test
async def test_search_queries_every_configured_provider_not_just_connected_ones(
    client, signed_up_user, db_session, monkeypatch
):
    """Regression: one workspace credential must not disable the others.

    `ApiProvider.connected` records "this workspace stored its own key" for the
    API Manager grid. It was also being used to *filter* which providers a search
    queried, so storing credentials for one provider silently excluded every
    provider configured through `.env` — a newly added key would test green and
    never be used.
    """
    from sqlalchemy import select, update

    from models.search import ApiProvider as ApiProviderModel

    # Exactly the broken state: one row flagged connected, the rest not.
    await db_session.execute(update(ApiProviderModel).values(connected=False))
    await db_session.execute(
        update(ApiProviderModel)
        .where(ApiProviderModel.name == "Mappls (MapmyIndia)")
        .values(connected=True)
    )
    await db_session.commit()

    # Geoapify is configured through settings only, and is NOT connected.
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "k", raising=False)
    _intercept(monkeypatch, {"geocode/search": GEOCODE_RESPONSE, "/places": PLACES_RESPONSE})

    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "dentists", "location": "Ahmedabad"}
    )
    assert resp.status_code == 201, resp.text

    queried = {run["provider_name"] for run in resp.json()["provider_runs"]}
    assert "Geoapify" in queried, (
        "a provider configured via settings must be queried even when another "
        f"provider is flagged connected; got {sorted(queried)}"
    )

    geoapify_run = next(
        run for run in resp.json()["provider_runs"] if run["provider_name"] == "Geoapify"
    )
    assert geoapify_run["status"] == "completed"
    assert geoapify_run["results_found"] == 1

    # And the lead it found carries coordinates.
    from models.lead import Company

    company = (
        await db_session.execute(
            select(Company).where(Company.name == "Premal Dental Clinic")
        )
    ).scalar_one()
    assert company.lat is not None and company.lng is not None


# --- Numeric-typed provider fields ---------------------------------------


def test_numeric_phone_from_openstreetmap_does_not_crash_dedup():
    """Regression: an all-digit OSM `phone` tag arrives as an int, not a string.

    `dedup.normalize_phone_key` called `re.sub` on it and raised
    "expected string or bytes-like object, got 'int'", turning a valid search
    into a 500. Found by running real Geoapify data through the pipeline.
    """
    from services.enrichment.dedup import normalize_phone_key
    from services.providers.base import NormalizedLead

    lead = NormalizedLead(company_name="Numeric Phone Co", phone=7912345678)
    # Coerced at the boundary...
    assert lead.phone == "7912345678"
    # ...and the shared helper is defensive regardless of who calls it.
    assert normalize_phone_key(7912345678) == "7912345678"
    assert normalize_phone_key("+91 79 1234 5678") == "7912345678"
    assert normalize_phone_key(None) == ""


def test_normalized_lead_coerces_and_trims_every_text_field():
    from services.providers.base import NormalizedLead

    lead = NormalizedLead(
        company_name="  Spaced Co  ",
        city=380022,          # OSM postcodes/cities arrive numeric too
        country="  India ",
        phone=7912345678,
        email="  a@b.test  ",
        gst_number=12345,
        address="  Some Road  ",
        website="  https://x.test  ",
    )
    assert lead.company_name == "Spaced Co"
    assert lead.city == "380022"
    assert lead.country == "India"
    assert lead.email == "a@b.test"
    assert lead.gst_number == "12345"
    assert lead.address == "Some Road"
    assert lead.website == "https://x.test"


def test_blank_strings_normalize_to_none():
    """An empty cell must not become "" — nullable columns mean "unknown"."""
    from services.providers.base import NormalizedLead

    lead = NormalizedLead(company_name="X", city="   ", phone="", website=None)
    assert lead.city is None
    assert lead.phone is None
    assert lead.website is None
