"""Provider adapter tests.

No network: each adapter's HTTP call is replaced with a fixture payload shaped
like the real API response, so these assert the *mapping* logic (which is where
adapter bugs actually live) without a paid API key.

The contract under test for every adapter:
  * unconfigured -> SKIPPED, never an exception and never a fabricated lead
  * provider error -> FAILED with a readable reason, siblings unaffected
  * success -> NormalizedLead values faithful to the payload
"""

import pytest

from services.providers import bing_search, google_places, mappls, registry, website_search
from services.providers.base import (
    NormalizedLead,
    ProviderRunStatus,
    SearchQuery,
)
from services.providers.http import PermanentProviderError, TransientProviderError


def _query(**overrides) -> SearchQuery:
    base = dict(query="switchgear manufacturers", location="Pune", industry="Electrical", country="India", max_results=5)
    base.update(overrides)
    return SearchQuery(**base)


# --- SearchQuery ---------------------------------------------------------


def test_full_text_combines_terms_without_duplicating_them():
    q = _query(query="switchgear manufacturers")
    assert q.full_text == "switchgear manufacturers Electrical in Pune"


def test_full_text_skips_terms_already_present_in_the_query():
    """Avoids "panels in Pune Panels in Pune", which degrades provider results."""
    q = _query(query="Electrical panels in Pune")
    assert q.full_text == "Electrical panels in Pune"


# --- NormalizedLead invariants ------------------------------------------


def test_rating_is_clamped_to_the_schema_range():
    """Numeric(2,1) and the frontend's star display both assume 0-5."""
    assert NormalizedLead(company_name="A", rating=9.7).rating == 5.0
    assert NormalizedLead(company_name="A", rating=-2).rating == 0.0
    assert NormalizedLead(company_name="A", rating=4.26).rating == 4.3


def test_overlong_strings_are_truncated_to_column_widths():
    lead = NormalizedLead(company_name="x" * 400, website="y" * 400, city="z" * 400)
    assert len(lead.company_name) == 255
    assert len(lead.website) == 255
    assert len(lead.city) == 150


# --- Google Places ------------------------------------------------------

PLACES_PAYLOAD = {
    "places": [
        {
            "id": "ChIJ_places_1",
            "displayName": {"text": "Apex Switchgear Pvt Ltd"},
            "formattedAddress": "Plot 12, MIDC, Bhosari, Pune, Maharashtra 411026, India",
            "addressComponents": [
                {"types": ["administrative_area_level_2"], "longText": "Pune"},
                {"types": ["country"], "longText": "India", "shortText": "IN"},
            ],
            "location": {"latitude": 18.6298, "longitude": 73.8398},
            "rating": 4.6,
            "websiteUri": "https://apexswitchgear.com",
            "internationalPhoneNumber": "+91 20 4567 8901",
            "primaryTypeDisplayName": {"text": "Electrical equipment supplier"},
            "businessStatus": "OPERATIONAL",
        },
        {
            "id": "ChIJ_places_closed",
            "displayName": {"text": "Defunct Panels Ltd"},
            "businessStatus": "CLOSED_PERMANENTLY",
        },
        {
            "id": "ChIJ_places_noname",
            "formattedAddress": "Somewhere",
        },
    ]
}


async def test_google_places_maps_a_place_to_a_lead(monkeypatch):
    captured = {}

    async def fake_request_json(method, url, *, params=None, json_body=None, form_body=None, headers=None, timeout=None):
        captured.update(method=method, url=url, body=json_body, headers=headers)
        return PLACES_PAYLOAD, 142

    monkeypatch.setattr(google_places, "request_json", fake_request_json)

    provider = google_places.GooglePlacesProvider(api_key="test-key")
    result = await provider.search(_query())

    assert result.status is ProviderRunStatus.COMPLETED
    assert result.latency_ms == 142
    # Closed and unnamed places are dropped, not passed through as leads.
    assert result.count == 1

    lead = result.leads[0]
    assert lead.company_name == "Apex Switchgear Pvt Ltd"
    assert lead.website == "https://apexswitchgear.com"
    assert lead.city == "Pune"
    assert lead.country == "India"
    assert lead.rating == 4.6
    assert lead.phone == "+91 20 4567 8901"
    assert lead.source_provider == "Google Places"
    assert lead.raw["place_id"] == "ChIJ_places_1"


async def test_google_places_populates_coordinates(monkeypatch):
    """Map Search renders searched leads only if lat/lng are real."""
    async def fake_request_json(*a, **k):
        return PLACES_PAYLOAD, 10

    monkeypatch.setattr(google_places, "request_json", fake_request_json)
    result = await google_places.GooglePlacesProvider(api_key="k").search(_query())
    lead = result.leads[0]
    assert (lead.lat, lead.lng) == (18.6298, 73.8398)


async def test_google_places_sends_the_mandatory_field_mask(monkeypatch):
    """Places API (New) returns 400 without X-Goog-FieldMask."""
    captured = {}

    async def fake_request_json(method, url, *, params=None, json_body=None, form_body=None, headers=None, timeout=None):
        captured.update(url=url, body=json_body, headers=headers)
        return {"places": []}, 5

    monkeypatch.setattr(google_places, "request_json", fake_request_json)
    await google_places.GooglePlacesProvider(api_key="k").search(_query())

    assert captured["url"] == google_places.SEARCH_TEXT_URL
    assert captured["headers"]["X-Goog-FieldMask"] == google_places.FIELD_MASK
    assert captured["headers"]["X-Goog-Api-Key"] == "k"
    assert captured["body"]["regionCode"] == "IN"


async def test_google_places_clamps_max_result_count(monkeypatch):
    """maxResultCount above 20 is rejected by the API."""
    captured = {}

    async def fake_request_json(method, url, *, params=None, json_body=None, form_body=None, headers=None, timeout=None):
        captured.update(body=json_body)
        return {"places": []}, 5

    monkeypatch.setattr(google_places, "request_json", fake_request_json)
    await google_places.GooglePlacesProvider(api_key="k").search(_query(max_results=500))
    assert captured["body"]["maxResultCount"] == google_places.MAX_RESULT_COUNT


async def test_google_places_skips_when_unconfigured(monkeypatch):
    monkeypatch.setattr(google_places.settings, "GOOGLE_MAPS_API_KEY", "", raising=False)
    provider = google_places.GooglePlacesProvider(api_key=None)
    assert provider.is_configured is False
    result = await provider.search(_query())
    assert result.status is ProviderRunStatus.SKIPPED
    assert result.leads == []


@pytest.mark.parametrize(
    "exc,expected_fragment",
    [
        (PermanentProviderError("Authentication rejected (401)"), "401"),
        (TransientProviderError("Timed out after 15s"), "Temporarily unavailable"),
    ],
)
async def test_google_places_converts_errors_to_failed_runs(monkeypatch, exc, expected_fragment):
    """An adapter must not raise — one dead provider can't fail the search."""
    async def fake_request_json(*a, **k):
        raise exc

    monkeypatch.setattr(google_places, "request_json", fake_request_json)
    result = await google_places.GooglePlacesProvider(api_key="k").search(_query())
    assert result.status is ProviderRunStatus.FAILED
    assert expected_fragment in result.error
    assert result.leads == []


def test_country_region_code_mapping():
    assert google_places._country_to_region_code("India") == "IN"
    assert google_places._country_to_region_code("de") == "DE"
    assert google_places._country_to_region_code("Atlantis") is None


def test_city_falls_back_to_the_formatted_address():
    """locality is absent on many Indian addresses."""
    city, country = google_places._city_country_from_components(
        [], "Plot 4, Andheri East, Mumbai, Maharashtra 400069, India"
    )
    assert country == "India"
    assert city == "Mumbai"


# --- Mappls -------------------------------------------------------------

MAPPLS_PAYLOAD = {
    "suggestedLocations": [
        {
            "placeName": "Nova Control Panels",
            "placeAddress": "Wagle Estate, Thane",
            "city": "Thane",
            "state": "Maharashtra",
            "latitude": "19.1934",
            "longitude": "72.9645",
            "eLoc": "ABC123",
            "mobileNo": "9876543210",
            "type": "Electrical",
        },
        {"placeAddress": "no name here"},
    ]
}


async def test_mappls_maps_suggestions_to_leads(monkeypatch):
    async def fake_request_json(method, url, *, params=None, json_body=None, form_body=None, headers=None, timeout=None):
        if url == mappls.TOKEN_URL:
            return {"access_token": "tok-1", "expires_in": 3600}, 20
        return MAPPLS_PAYLOAD, 88

    monkeypatch.setattr(mappls, "request_json", fake_request_json)
    mappls._TokenCache._tokens.clear()

    result = await mappls.MapplsProvider(client_id="cid", client_secret="secret").search(_query())

    assert result.status is ProviderRunStatus.COMPLETED
    assert result.count == 1  # the nameless suggestion is dropped
    lead = result.leads[0]
    assert lead.company_name == "Nova Control Panels"
    assert lead.city == "Thane"
    assert lead.country == "India"
    assert (lead.lat, lead.lng) == (19.1934, 72.9645)
    assert lead.phone == "9876543210"
    assert lead.raw["eloc"] == "ABC123"


async def test_mappls_caches_the_oauth_token_across_searches(monkeypatch):
    """A burst of searches must not perform one token exchange each."""
    token_calls = {"n": 0}

    async def fake_request_json(method, url, *, params=None, json_body=None, form_body=None, headers=None, timeout=None):
        if url == mappls.TOKEN_URL:
            token_calls["n"] += 1
            return {"access_token": "tok-1", "expires_in": 3600}, 20
        return {"suggestedLocations": []}, 10

    monkeypatch.setattr(mappls, "request_json", fake_request_json)
    mappls._TokenCache._tokens.clear()

    provider = mappls.MapplsProvider(client_id="cid-cache", client_secret="s")
    await provider.search(_query())
    await provider.search(_query())
    await provider.search(_query())

    assert token_calls["n"] == 1


async def test_mappls_discards_a_token_the_server_rejected(monkeypatch):
    """Otherwise every later search replays a dead token."""
    async def fake_request_json(method, url, *, params=None, json_body=None, form_body=None, headers=None, timeout=None):
        if url == mappls.TOKEN_URL:
            return {"access_token": "stale", "expires_in": 3600}, 5
        raise PermanentProviderError("Authentication rejected (401)")

    monkeypatch.setattr(mappls, "request_json", fake_request_json)
    mappls._TokenCache._tokens.clear()

    provider = mappls.MapplsProvider(client_id="cid-evict", client_secret="s")
    result = await provider.search(_query())

    assert result.status is ProviderRunStatus.FAILED
    assert "cid-evict" not in mappls._TokenCache._tokens


async def test_mappls_skips_when_unconfigured(monkeypatch):
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_ID", "", raising=False)
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_SECRET", "", raising=False)
    result = await mappls.MapplsProvider().search(_query())
    assert result.status is ProviderRunStatus.SKIPPED


# --- Bing Search --------------------------------------------------------

BING_PAYLOAD = {
    "webPages": {
        "value": [
            {
                "name": "Apex Switchgear | LT Panel Manufacturer in Pune",
                "url": "https://www.apexswitchgear.com/",
                "snippet": "LT panels and switchgear.",
            },
            # Aggregator: its contact details are not the company's.
            {"name": "Switchgear Manufacturers", "url": "https://www.indiamart.com/x"},
            {"name": "Apex on LinkedIn", "url": "https://in.linkedin.com/company/apex"},
            # Second page on a domain already seen -> one lead per company.
            {"name": "Apex Switchgear - Contact Us", "url": "https://apexswitchgear.com/contact"},
            {"name": "Nova Panels Pvt Ltd - Home", "url": "https://novapanels.co.in/"},
        ]
    }
}


async def test_bing_maps_pages_to_company_leads(monkeypatch):
    async def fake_request_json(method, url, *, params=None, json_body=None, form_body=None, headers=None, timeout=None):
        return BING_PAYLOAD, 60

    monkeypatch.setattr(bing_search, "request_json", fake_request_json)
    result = await bing_search.BingSearchProvider(api_key="k").search(_query())

    assert result.status is ProviderRunStatus.COMPLETED
    names = [l.company_name for l in result.leads]
    # The legal suffix is preserved here; dedup is what normalizes it away.
    assert names == ["Apex Switchgear", "Nova Panels Pvt Ltd"]


async def test_bing_excludes_aggregators_and_social_sites(monkeypatch):
    async def fake_request_json(*a, **k):
        return BING_PAYLOAD, 10

    monkeypatch.setattr(bing_search, "request_json", fake_request_json)
    result = await bing_search.BingSearchProvider(api_key="k").search(_query())
    hosts = [l.website for l in result.leads]
    assert not any("indiamart" in h or "linkedin" in h for h in hosts)


async def test_bing_over_fetches_to_survive_aggregator_filtering(monkeypatch):
    captured = {}

    async def fake_request_json(method, url, *, params=None, json_body=None, form_body=None, headers=None, timeout=None):
        captured.update(params=params, headers=headers)
        return {"webPages": {"value": []}}, 5

    monkeypatch.setattr(bing_search, "request_json", fake_request_json)
    await bing_search.BingSearchProvider(api_key="k").search(_query(max_results=5))

    assert captured["params"]["count"] == 20
    assert captured["params"]["mkt"] == "en-IN"
    assert captured["headers"]["Ocp-Apim-Subscription-Key"] == "k"


async def test_bing_respects_max_results(monkeypatch):
    many = {"webPages": {"value": [
        {"name": f"Company {i} Ltd", "url": f"https://company{i}.com/"} for i in range(30)
    ]}}

    async def fake_request_json(*a, **k):
        return many, 5

    monkeypatch.setattr(bing_search, "request_json", fake_request_json)
    result = await bing_search.BingSearchProvider(api_key="k").search(_query(max_results=3))
    assert result.count == 3


async def test_bing_skips_when_unconfigured(monkeypatch):
    monkeypatch.setattr(bing_search.settings, "BING_SEARCH_API_KEY", "", raising=False)
    result = await bing_search.BingSearchProvider(api_key=None).search(_query())
    assert result.status is ProviderRunStatus.SKIPPED
    # The retirement caveat must reach the operator, not just the module docstring.
    assert "retired" in result.error


@pytest.mark.parametrize(
    "host,expected",
    [
        ("apexswitchgear.com", "apexswitchgear.com"),
        ("shop.nova.co.in", "nova.co.in"),
        ("www.nova.co.in", "nova.co.in"),
        ("a.b.example.com", "example.com"),
    ],
)
def test_registrable_domain(host, expected):
    assert bing_search._registrable_domain(host) == expected


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Apex Switchgear | LT Panels", "Apex Switchgear"),
        ("Nova Panels Pvt Ltd - Home", "Nova Panels Pvt Ltd"),
        ("Welcome", "Acme Tools"),          # noise-only title -> derive from domain
        (None, "Acme Tools"),
    ],
)
def test_company_name_from_page(title, expected):
    assert bing_search._company_name_from_page(title, "acme-tools.com") == expected


# --- Company Website Search --------------------------------------------

HOMEPAGE = """
<html><head><title>Nova Panels | Switchgear</title>
<meta name="description" content="Panel builders"><meta name="viewport" content="width=device-width">
<meta property="og:site_name" content="Nova Panels"></head>
<body><h1>Nova Panels</h1><img src="a.png" alt="logo">
<a href="/contact">Contact Us</a>
<a href="https://someoneelse.com/contact">Partner contact</a>
</body></html>
"""

CONTACT_PAGE = """
<html><body>
<p>Email <a href="mailto:sales@novapanels.co.in">sales@novapanels.co.in</a></p>
<p>Phone 020-4567-8901 / 9876543210</p>
<p>GSTIN: 27AAPFU0939F1ZV</p>
</body></html>
"""


class _FakeFetch:
    """Stands in for safe_fetch, serving fixture HTML per URL."""

    def __init__(self, pages: dict[str, str], status: int = 200):
        self.pages = pages
        self.status = status
        self.requested: list[str] = []

    async def __call__(self, url, **kwargs):
        self.requested.append(url)
        # Mirror the real guard, which defaults a scheme-less host to https://
        # before fetching — contact-page discovery depends on final_url being
        # absolute, so a fake that skipped this would hide real behaviour.
        final_url = url if "://" in url else f"https://{url}"
        for key, html in self.pages.items():
            if final_url.rstrip("/").endswith(key.rstrip("/")) or final_url == key:
                return _fetch_result(final_url, html, self.status)
        raise website_search.FetchError("Not found", kind="http")


def _fetch_result(url: str, html: str, status: int = 200):
    from services.safe_http import FetchResult

    return FetchResult(
        final_url=url,
        status_code=status,
        content=html.encode(),
        headers={"content-type": "text/html; charset=utf-8"},
        elapsed_ms=25,
        tls_used=url.startswith("https://"),
    )


async def test_website_profile_extracts_real_contact_details(monkeypatch):
    fetch = _FakeFetch(
        {
            "https://novapanels.co.in": HOMEPAGE,
            "/contact": CONTACT_PAGE,
        }
    )
    monkeypatch.setattr(website_search, "safe_fetch", fetch)

    profile = await website_search.build_website_profile("https://novapanels.co.in", max_pages=3)

    assert profile.succeeded
    assert profile.company_name == "Nova Panels"
    assert "sales@novapanels.co.in" in profile.emails
    assert "+919876543210" in profile.phones
    assert "+912045678901" in profile.phones
    assert profile.gstin == "27AAPFU0939F1ZV"
    assert profile.pages_crawled == 2
    assert profile.ssl_valid is True
    assert profile.mobile_friendly is True
    assert profile.seo_score > 0


async def test_website_crawl_stays_on_the_same_origin(monkeypatch):
    """Following off-site links would attribute another company's contacts."""
    fetch = _FakeFetch({"https://novapanels.co.in": HOMEPAGE, "/contact": CONTACT_PAGE})
    monkeypatch.setattr(website_search, "safe_fetch", fetch)

    await website_search.build_website_profile("https://novapanels.co.in", max_pages=5)

    assert not any("someoneelse.com" in url for url in fetch.requested)


async def test_website_crawl_budget_is_respected(monkeypatch):
    fetch = _FakeFetch({"https://novapanels.co.in": HOMEPAGE, "/contact": CONTACT_PAGE})
    monkeypatch.setattr(website_search, "safe_fetch", fetch)

    profile = await website_search.build_website_profile("https://novapanels.co.in", max_pages=1)

    assert profile.pages_crawled == 1
    assert len(fetch.requested) == 1


async def test_unreachable_site_reports_failure_instead_of_fabricating(monkeypatch):
    async def failing_fetch(url, **kwargs):
        raise website_search.FetchError("Connection refused", kind="network")

    monkeypatch.setattr(website_search, "safe_fetch", failing_fetch)

    profile = await website_search.build_website_profile("https://down.example.com")

    assert profile.succeeded is False
    assert "Connection refused" in profile.error
    assert profile.emails == []
    assert profile.gstin is None


async def test_unsafe_url_propagates_from_the_profile_builder(monkeypatch):
    from utils.exceptions import UnsafeUrlError

    async def blocked_fetch(url, **kwargs):
        raise UnsafeUrlError("Blocked private address")

    monkeypatch.setattr(website_search, "safe_fetch", blocked_fetch)

    with pytest.raises(UnsafeUrlError):
        await website_search.build_website_profile("http://169.254.169.254/")


async def test_website_provider_turns_a_domain_in_the_query_into_a_lead(monkeypatch):
    fetch = _FakeFetch({"novapanels.co.in": HOMEPAGE, "/contact": CONTACT_PAGE})
    monkeypatch.setattr(website_search, "safe_fetch", fetch)

    provider = website_search.WebsiteSearchProvider(max_pages=3)
    result = await provider.search(_query(query="check novapanels.co.in please"))

    assert result.status is ProviderRunStatus.COMPLETED
    assert result.count == 1
    lead = result.leads[0]
    assert lead.email == "sales@novapanels.co.in"
    assert lead.gst_number == "27AAPFU0939F1ZV"
    assert lead.source_provider == "Company Website Search"


async def test_website_provider_skips_a_query_with_no_domain(monkeypatch):
    provider = website_search.WebsiteSearchProvider()
    result = await provider.search(_query(query="switchgear manufacturers in Pune"))
    assert result.status is ProviderRunStatus.SKIPPED
    assert result.leads == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ("visit apexswitchgear.com today", ["apexswitchgear.com"]),
        ("https://nova.co.in/contact", ["https://nova.co.in/contact"]),
        ("no domain here", []),
        ("a.com and b.co.in", ["a.com", "b.co.in"]),
    ],
)
def test_domain_extraction_from_query_text(text, expected):
    assert website_search._extract_domains(text) == expected


def test_own_domain_emails_rank_first():
    """A gmail address on a corporate site is more often an agency's."""
    ranked = website_search._prefer_own_domain(
        ["agency@gmail.com", "sales@novapanels.co.in"], "novapanels.co.in"
    )
    assert ranked[0] == "sales@novapanels.co.in"


# --- Registry -----------------------------------------------------------


def test_registry_returns_no_adapter_for_enrichment_only_providers():
    from models.enums import ProviderCategory, ProviderStatus
    from models.search import ApiProvider

    row = ApiProvider(
        name="OpenAI GPT", category=ProviderCategory.AI, status=ProviderStatus.HEALTHY, connected=True
    )
    assert registry.build_adapter(row) is None


def test_registry_skips_unconfigured_adapters(monkeypatch):
    """No credentials -> not offered, so credits are never spent on a doomed call."""
    from models.enums import ProviderCategory, ProviderStatus
    from models.search import ApiProvider

    monkeypatch.setattr(google_places.settings, "GOOGLE_MAPS_API_KEY", "", raising=False)
    monkeypatch.setattr(bing_search.settings, "BING_SEARCH_API_KEY", "", raising=False)
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_ID", "", raising=False)
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_SECRET", "", raising=False)
    monkeypatch.setattr(website_search.settings, "SCANNER_ENABLED", False, raising=False)

    rows = [
        ApiProvider(name=name, category=ProviderCategory.SEARCH, status=ProviderStatus.HEALTHY, connected=True)
        for name in registry.LEAD_SOURCE_NAMES
    ]
    assert registry.resolve_lead_providers(rows) == []


def test_registry_resolves_a_configured_adapter(monkeypatch):
    from models.enums import ProviderCategory, ProviderStatus
    from models.search import ApiProvider

    monkeypatch.setattr(google_places.settings, "GOOGLE_MAPS_API_KEY", "platform-key", raising=False)
    row = ApiProvider(
        name="Google Places", category=ProviderCategory.MAPS, status=ProviderStatus.HEALTHY, connected=True
    )
    resolved = registry.resolve_lead_providers([row])
    assert len(resolved) == 1
    assert resolved[0][1].name == "Google Places"


def test_registry_tolerates_an_undecryptable_stored_credential(monkeypatch):
    """A rotated/retired key must degrade to the platform key, not break search."""
    from models.enums import ProviderCategory, ProviderStatus
    from models.search import ApiProvider

    monkeypatch.setattr(google_places.settings, "GOOGLE_MAPS_API_KEY", "platform-key", raising=False)
    row = ApiProvider(
        name="Google Places",
        category=ProviderCategory.MAPS,
        status=ProviderStatus.HEALTHY,
        connected=True,
        api_key_encrypted="not-a-valid-fernet-token",
    )
    adapter = registry.build_adapter(row)
    assert adapter is not None
    assert adapter.is_configured is True


# --- Mappls: the response shape the live API actually returns -------------

# Captured verbatim from https://atlas.mappls.com/api/places/textsearch/json
# for "Restaurants in Ahmedabad". Note what is absent: latitude/longitude and
# any discrete city field. MAPPLS_PAYLOAD above is the documented shape (a
# project licensed for coordinate delivery); this is the unlicensed shape, and
# both must produce usable leads.
MAPPLS_LIVE_PAYLOAD = {
    "suggestedLocations": [
        {
            "distance": 42,
            "eLoc": "ZKQFP8",
            "keywords": ["FODOTH"],
            "orderIndex": 1,
            "placeAddress": "Swami Vivekanand Road, Kagdapith, Raipur, Ahmedabad, Gujarat, 380022",
            "placeName": "Apple Foods",
            "type": "POI",
        },
        {
            "distance": 145,
            "eLoc": "XB5HVV",
            "keywords": ["FODOTH"],
            "orderIndex": 2,
            "placeAddress": "New Cloth Market, Sarangpur, Ahmedabad, Gujarat, 380001",
            "placeName": "JD's Snacks",
            "type": "POI",
        },
        # Mappls mixes the city itself into the results; it is not a business.
        {
            "eLoc": "GWRWKL",
            "placeAddress": "Gujarat",
            "placeName": "Ahmedabad",
            "type": "CITY",
        },
    ]
}


def _mappls_fake(payload):
    async def fake_request_json(method, url, *, params=None, json_body=None, form_body=None, headers=None, timeout=None):
        if url == mappls.TOKEN_URL:
            # The credentials must travel in the body, not the query string,
            # so the secret cannot leak into proxy/access logs.
            assert form_body is not None and params is None
            assert form_body["grant_type"] == "client_credentials"
            return {"access_token": "tok", "expires_in": 82852, "scope": "READ"}, 20
        assert headers and headers.get("Authorization") == "Bearer tok"
        return payload, 90

    return fake_request_json


async def test_mappls_parses_the_live_response_shape(monkeypatch):
    monkeypatch.setattr(mappls, "request_json", _mappls_fake(MAPPLS_LIVE_PAYLOAD))
    mappls._TokenCache._tokens.clear()

    result = await mappls.MapplsProvider(client_id="cid-live", client_secret="s").search(_query())

    assert result.status is ProviderRunStatus.COMPLETED
    # The CITY row is dropped; the two POIs survive.
    assert [lead.company_name for lead in result.leads] == ["Apple Foods", "JD's Snacks"]

    lead = result.leads[0]
    # City/state/pincode are not discrete fields — they come out of placeAddress.
    assert lead.city == "Ahmedabad"
    assert lead.raw["state"] == "Gujarat"
    assert lead.raw["pincode"] == "380022"
    assert lead.raw["eloc"] == "ZKQFP8"
    assert lead.country == "India"
    # No coordinates on an unlicensed project — and that must not be faked.
    assert lead.lat is None and lead.lng is None


async def test_mappls_falls_back_to_the_searched_location_for_city(monkeypatch):
    """An address with too few components must not leave the lead city-less."""
    payload = {"suggestedLocations": [{"placeName": "Corner Shop", "placeAddress": "Gujarat", "type": "POI"}]}
    monkeypatch.setattr(mappls, "request_json", _mappls_fake(payload))
    mappls._TokenCache._tokens.clear()

    result = await mappls.MapplsProvider(client_id="cid-city", client_secret="s").search(_query())
    assert result.leads[0].city == _query().location


async def test_mappls_reverse_geocode_normalizes_string_coordinates(monkeypatch):
    """Mappls echoes lat/lng back as strings; callers expect floats."""
    payload = {
        "responseCode": 200,
        "results": [
            {
                "lat": "23.0225",
                "lng": "72.5714",
                "formatted_address": "Ellis Bridge Road, Ahmedabad, Gujarat. Pin-380006 (India)",
            }
        ],
    }
    monkeypatch.setattr(mappls, "request_json", _mappls_fake(payload))
    mappls._TokenCache._tokens.clear()

    out = await mappls.MapplsClient(client_id="cid-rev", client_secret="s").reverse_geocode(23.0225, 72.5714)
    assert out == {
        "lat": 23.0225,
        "lng": 72.5714,
        "formatted_address": "Ellis Bridge Road, Ahmedabad, Gujarat. Pin-380006 (India)",
    }


async def test_mappls_geocode_without_coordinates_raises_rather_than_reporting_no_match(monkeypatch):
    """An unlicensed project returns a match with no lat/lng.

    Reporting that as "address not found" would send the operator hunting for a
    data problem that does not exist, so it must surface as an auth/entitlement
    error carrying the real response.
    """
    payload = {"copResults": {"formattedAddress": "Ahmedabad, Gujarat", "eLoc": "GWRWKL"}}
    monkeypatch.setattr(mappls, "request_json", _mappls_fake(payload))
    mappls._TokenCache._tokens.clear()

    with pytest.raises(mappls.MapplsAuthError) as exc:
        await mappls.MapplsClient(client_id="cid-geo", client_secret="s").geocode("Ahmedabad")

    assert "not licensed" in str(exc.value)
    assert "GWRWKL" in str(exc.value), "the real provider response must be included"


async def test_mappls_geocode_returns_coordinates_when_licensed(monkeypatch):
    payload = {
        "copResults": {
            "formattedAddress": "Ahmedabad, Gujarat",
            "latitude": 23.0225,
            "longitude": 72.5714,
        }
    }
    monkeypatch.setattr(mappls, "request_json", _mappls_fake(payload))
    mappls._TokenCache._tokens.clear()

    out = await mappls.MapplsClient(client_id="cid-geo2", client_secret="s").geocode("Ahmedabad")
    assert out == {"lat": 23.0225, "lng": 72.5714, "formatted_address": "Ahmedabad, Gujarat"}
