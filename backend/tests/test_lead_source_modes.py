"""Lead Source: Map / API / Auto routing, and the Map Mode review flow.

Only the providers' outbound HTTP is faked. Mode selection, credit metering,
deduplication, scoring and persistence all run for real, because those are the
parts the feature is claiming to keep intact.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from models.lead import Lead
from models.organization import Organization

asyncio_test = pytest.mark.asyncio(loop_scope="session")

# Two Overpass elements with everything a lead needs, and one with only a name —
# real OSM data is mostly the latter.
OVERPASS_PAYLOAD = {
    "elements": [
        {
            "type": "node",
            "id": 1001,
            "lat": 23.2599,
            "lon": 77.4126,
            "tags": {
                "name": "Sunrise Diagnostics",
                "amenity": "hospital",
                "phone": "+91 755 400 1001",
                "website": "https://sunrise-diagnostics.example.com",
                "addr:city": "Bhopal, Madhya Pradesh 462003",
            },
        },
        {
            "type": "node",
            "id": 1002,
            "lat": 23.2610,
            "lon": 77.4140,
            "tags": {"name": "Cedar Clinic", "amenity": "clinic", "addr:city": "Bhopal"},
        },
    ]
}

NOMINATIM_PAYLOAD = [
    {
        "place_id": 5001,
        "lat": "23.2599",
        "lon": "77.4126",
        "display_name": "Northgate Medical, Bhopal",
        "name": "Northgate Medical",
        "type": "hospital",
        "address": {"city": "Bhopal", "country": "India"},
    }
]

PLACES_PAYLOAD = {
    "places": [
        {
            "displayName": {"text": "Apex Care Hospital"},
            "formattedAddress": "12 MG Road, Bhopal, India",
            "nationalPhoneNumber": "+91 755 900 2002",
            "websiteUri": "https://apexcare.example.com",
            "location": {"latitude": 23.25, "longitude": 77.40},
            "rating": 4.4,
        }
    ]
}


@pytest.fixture
def providers(monkeypatch):
    """Configures one API provider and both map providers, recording who ran.

    Returns the `called` set so a test can assert which side of the split was
    actually queried — which is the whole point of a mode.
    """
    from services.providers import bing_search, geoapify, google_places, mappls
    from services.providers import openstreetmap, osm_common, overpass, website_search

    called: set[str] = set()

    # `**kwargs` on purpose: these stand in for `providers.http.request_json`,
    # whose callers pass different keyword sets (`params`, `json_body`,
    # `form_body`). Pinning an exact signature made Overpass raise TypeError and
    # be recorded as a provider failure rather than as "never ran".
    async def fake_places(method, url, **kwargs):
        called.add("Google Places")
        return PLACES_PAYLOAD, 40

    async def fake_osm(method, url, **kwargs):
        called.add("OpenStreetMap")
        return NOMINATIM_PAYLOAD, 30

    async def fake_overpass(method, url, **kwargs):
        called.add("Overpass API")
        return OVERPASS_PAYLOAD, 50

    monkeypatch.setattr(google_places.settings, "GOOGLE_MAPS_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(google_places, "request_json", fake_places)

    monkeypatch.setattr(openstreetmap.settings, "OSM_USER_AGENT", "LeadMasterAI/1.0", raising=False)
    monkeypatch.setattr(overpass.settings, "OSM_USER_AGENT", "LeadMasterAI/1.0", raising=False)
    monkeypatch.setattr(
        overpass.settings, "OVERPASS_URL", "https://overpass.test/api/interpreter", raising=False
    )
    monkeypatch.setattr(openstreetmap, "request_json", fake_osm)
    monkeypatch.setattr(overpass, "request_json", fake_overpass)
    # Nominatim's rate limiter would serialise these; the tests are not measuring it.
    monkeypatch.setattr(osm_common.nominatim_limiter, "min_interval", 0.0, raising=False)

    # Both caches are process-wide and live for 15 minutes, so without this the
    # second test to ask for "hospital near Bhopal" gets a cache hit, never calls
    # the fake, and looks like the provider was never routed to at all.
    osm_common.nominatim_cache._entries.clear()
    osm_common.overpass_cache._entries.clear()

    # Keep the provider set to exactly what each test reasons about.
    monkeypatch.setattr(website_search.settings, "SCANNER_ENABLED", False, raising=False)
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_ID", "", raising=False)
    monkeypatch.setattr(geoapify.settings, "GEOAPIFY_API_KEY", "", raising=False)
    monkeypatch.setattr(bing_search.settings, "BING_SEARCH_API_KEY", "", raising=False)

    return called


async def _org_id(db_session) -> uuid.UUID:
    stmt = select(Organization).order_by(Organization.created_at.desc()).limit(1)
    return (await db_session.execute(stmt)).scalar_one().id


# --- Mode routing ---------------------------------------------------------


@asyncio_test
async def test_map_mode_uses_only_public_map_providers(client: AsyncClient, signed_up_user, providers):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "hospital", "location": "Bhopal", "mode": "map"}
    )
    assert resp.status_code == 201, resp.text

    assert providers == {"OpenStreetMap", "Overpass API"}
    assert "Google Places" not in providers, "Map Mode must not call a credentialed API"


@asyncio_test
async def test_api_mode_uses_only_configured_providers(client: AsyncClient, signed_up_user, providers):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "hospital", "location": "Bhopal", "mode": "api"}
    )
    assert resp.status_code == 201, resp.text

    assert "Google Places" in providers
    assert "Overpass API" not in providers
    assert "OpenStreetMap" not in providers


@asyncio_test
async def test_auto_mode_does_not_touch_map_when_the_api_returns_results(
    client: AsyncClient, signed_up_user, providers
):
    """The explicit rule: don't spend Map Mode resources on a successful API run."""
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "hospital", "location": "Bhopal", "mode": "auto"}
    )
    assert resp.status_code == 201, resp.text

    assert "Google Places" in providers
    assert "Overpass API" not in providers
    assert "OpenStreetMap" not in providers


@asyncio_test
async def test_auto_mode_falls_back_to_map_when_the_api_returns_nothing(
    client: AsyncClient, signed_up_user, providers, monkeypatch
):
    from services.providers import google_places

    async def empty_places(method, url, **kwargs):
        providers.add("Google Places")
        return {"places": []}, 40

    monkeypatch.setattr(google_places, "request_json", empty_places)

    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "hospital", "location": "Bhopal", "mode": "auto"}
    )
    assert resp.status_code == 201, resp.text

    assert "Google Places" in providers, "the API side must be tried first"
    assert "Overpass API" in providers, "and the map fallback must then run"


@asyncio_test
async def test_omitting_the_mode_keeps_the_previous_behaviour(
    client: AsyncClient, signed_up_user, providers
):
    """Backward compatibility: existing clients send no mode and query everything."""
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "hospital", "location": "Bhopal"}
    )
    assert resp.status_code == 201, resp.text

    assert {"Google Places", "OpenStreetMap", "Overpass API"} <= providers


@asyncio_test
async def test_an_unknown_mode_is_rejected(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "hospital", "mode": "telepathy"}
    )
    assert resp.status_code == 422


# --- Credits --------------------------------------------------------------


@asyncio_test
async def test_a_provider_that_never_ran_is_not_charged_for(
    client: AsyncClient, signed_up_user, providers, db_session
):
    """Auto reserves for the fallback but must settle only against what ran."""
    from models.billing import CreditWallet

    _, headers = signed_up_user
    org_id = await _org_id(db_session)

    async def balance() -> int:
        db_session.expire_all()
        stmt = select(CreditWallet.balance).where(CreditWallet.organization_id == org_id)
        return (await db_session.execute(stmt)).scalar_one()

    before = await balance()
    resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "hospital", "location": "Bhopal", "mode": "auto"}
    )
    assert resp.status_code == 201, resp.text
    after = await balance()

    # The map providers were reserved for (the fallback might have run) but never
    # called, so the settled cost must reflect only the API results.
    results = resp.json()["results_count"]
    spent = before - after
    assert "Overpass API" not in providers
    assert spent <= results * 2, f"charged {spent} for {results} API-sourced results"


# --- Source metadata ------------------------------------------------------


@asyncio_test
async def test_map_leads_are_labelled_map_and_api_leads_api(
    client: AsyncClient, signed_up_user, providers, db_session
):
    _, headers = signed_up_user
    org_id = await _org_id(db_session)

    await client.post(
        "/api/v1/search", headers=headers, json={"query": "hospital", "location": "Bhopal", "mode": "map"}
    )
    rows = (
        await db_session.execute(
            select(Lead.source_type, Lead.source_provider).where(Lead.organization_id == org_id)
        )
    ).all()

    assert rows, "the map search should have produced leads"
    assert {r[0] for r in rows} == {"map"}
    assert {r[1] for r in rows} <= {"OpenStreetMap", "Overpass API"}


# --- Map Mode extract / import -------------------------------------------


@asyncio_test
async def test_extract_returns_public_results_without_saving_them(
    client: AsyncClient, signed_up_user, providers, db_session
):
    """The review step: look before anything is written."""
    _, headers = signed_up_user
    org_id = await _org_id(db_session)

    resp = await client.post(
        "/api/v1/map/extract", headers=headers, json={"query": "hospital", "location": "Bhopal"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["results"], "expected public results"
    assert body["blocked_reason"] is None
    assert "Google Places" not in providers, "extraction is map-only"

    count = (
        await db_session.execute(select(Lead).where(Lead.organization_id == org_id))
    ).scalars().all()
    assert count == [], "extract must not persist anything"


@asyncio_test
async def test_extract_never_invents_missing_fields(client: AsyncClient, signed_up_user, providers):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/map/extract", headers=headers, json={"query": "hospital", "location": "Bhopal"}
    )
    results = {r["company_name"]: r for r in resp.json()["results"]}

    # Cedar Clinic is tagged with a name and nothing else.
    cedar = results.get("Cedar Clinic")
    assert cedar is not None
    assert cedar["phone"] is None
    assert cedar["website"] is None
    assert cedar["email"] is None
    # What OSM does publish is carried through.
    assert cedar["latitude"] is not None


@asyncio_test
async def test_importing_a_selection_creates_leads_through_the_normal_pipeline(
    client: AsyncClient, signed_up_user, providers, db_session
):
    _, headers = signed_up_user
    org_id = await _org_id(db_session)

    extracted = (
        await client.post(
            "/api/v1/map/extract", headers=headers, json={"query": "hospital", "location": "Bhopal"}
        )
    ).json()["results"]

    resp = await client.post(
        "/api/v1/map/import", headers=headers, json={"results": extracted[:2]}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["imported"] == 2

    rows = (
        await db_session.execute(
            select(Lead).where(Lead.organization_id == org_id)
        )
    ).scalars().all()
    assert len(rows) == 2
    # Scored and labelled like any other lead.
    assert all(r.source_type == "map" for r in rows)
    assert all(r.lead_score >= 0 for r in rows)


@asyncio_test
async def test_importing_the_same_selection_twice_creates_no_duplicates(
    client: AsyncClient, signed_up_user, providers, db_session
):
    """A city stored as "Bhopal, Madhya Pradesh 462003" used to defeat dedup.

    Candidate lookup compared the *normalized* city ("bhopal") against the raw
    lowercased column, so rows with an address-style city were never loaded as
    candidates and the duplicate was admitted.
    """
    _, headers = signed_up_user
    org_id = await _org_id(db_session)

    extracted = (
        await client.post(
            "/api/v1/map/extract", headers=headers, json={"query": "hospital", "location": "Bhopal"}
        )
    ).json()["results"]

    first = await client.post("/api/v1/map/import", headers=headers, json={"results": extracted})
    second = await client.post("/api/v1/map/import", headers=headers, json={"results": extracted})

    assert first.json()["imported"] > 0
    assert second.json()["imported"] == 0
    assert second.json()["duplicates"] == first.json()["imported"]

    rows = (
        await db_session.execute(select(Lead).where(Lead.organization_id == org_id))
    ).scalars().all()
    assert len(rows) == first.json()["imported"]


@asyncio_test
async def test_importing_nothing_is_rejected(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post("/api/v1/map/import", headers=headers, json={"results": []})
    assert resp.status_code == 422


@asyncio_test
async def test_map_endpoints_require_authentication(client: AsyncClient):
    extract = await client.post("/api/v1/map/extract", json={"query": "hospital"})
    assert extract.status_code in (401, 403)
