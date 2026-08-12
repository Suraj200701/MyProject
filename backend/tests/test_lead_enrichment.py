"""Contact enrichment: discovery, merge rules, provenance, bulk and credits.

The website crawl is stubbed so these are deterministic and offline; discovery,
merging, status transitions, provenance and credit settlement all run for real.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from models.enums import EnrichmentStatus
from models.lead import Company, Lead
from models.organization import Organization
from services.providers.website_search import WebsiteProfile

asyncio_test = pytest.mark.asyncio(loop_scope="session")


def _profile(**over) -> WebsiteProfile:
    base = dict(
        url="https://acme-switchgear.example.com/",
        domain="acme-switchgear.example.com",
        company_name="Acme Switchgear",
        emails=["sales@acme-switchgear.example.com"],
        phones=["+912045678901"],
        gstin="24AAACC1206D1ZM",
        social_links=[{"platform": "LinkedIn", "found": True, "handle": "@company/acme"}],
        http_status=200,
        pages_crawled=2,
        field_sources={
            "sales@acme-switchgear.example.com": "https://acme-switchgear.example.com/contact",
            "+912045678901": "https://acme-switchgear.example.com/contact",
            "24AAACC1206D1ZM": "https://acme-switchgear.example.com/about",
            "social:LinkedIn": "https://acme-switchgear.example.com/",
        },
    )
    base.update(over)
    return WebsiteProfile(**base)


@pytest.fixture
def crawl(monkeypatch):
    """Stubs the crawl and records which URLs were fetched."""
    from services.enrichment import lead_enrichment

    fetched: list[str] = []

    async def fake_build(url, max_pages=None):
        fetched.append(url)
        return _profile()

    monkeypatch.setattr(lead_enrichment, "build_website_profile", fake_build)
    return fetched


@pytest.fixture
def places_off(monkeypatch):
    """Google Places unconfigured — the optional path."""
    from services.enrichment import website_discovery

    monkeypatch.setattr(website_discovery.settings, "GOOGLE_MAPS_API_KEY", "", raising=False)
    website_discovery._DISCOVERY_CACHE._entries.clear()


@pytest.fixture
def places_on(monkeypatch):
    """Google Places configured, answering with one place."""
    from services.enrichment import website_discovery

    monkeypatch.setattr(website_discovery.settings, "GOOGLE_MAPS_API_KEY", "test-key", raising=False)
    website_discovery._DISCOVERY_CACHE._entries.clear()

    calls: list[dict] = []

    async def fake_request_json(method, url, **kwargs):
        calls.append(kwargs.get("json_body") or {})
        return {
            "places": [
                {
                    "id": "places/abc",
                    "displayName": {"text": "Acme Switchgear"},
                    "websiteUri": "https://acme-switchgear.example.com/",
                    "formattedAddress": "12 MG Road, Bhopal, India",
                    "nationalPhoneNumber": "+91 20 4567 8901",
                }
            ]
        }, 30

    monkeypatch.setattr(website_discovery, "request_json", fake_request_json)
    return calls


async def _org_id(db_session) -> uuid.UUID:
    stmt = select(Organization).order_by(Organization.created_at.desc()).limit(1)
    return (await db_session.execute(stmt)).scalar_one().id


async def _make_lead(db_session, org_id, *, name="Acme Switchgear", website=None, phone=None, email=None):
    company = Company(name=name, city="Bhopal", website=website)
    db_session.add(company)
    await db_session.flush()
    lead = Lead(organization_id=org_id, company_id=company.id, phone=phone, email=email, lead_score=10)
    db_session.add(lead)
    await db_session.commit()
    await db_session.refresh(lead)
    return lead


# --- Discovery ------------------------------------------------------------


@asyncio_test
async def test_a_lead_with_a_website_is_not_searched_again(
    client: AsyncClient, signed_up_user, db_session, crawl, places_on
):
    """Discovery costs a Places call, so it must be skipped when redundant."""
    _, headers = signed_up_user
    lead = await _make_lead(
        db_session, await _org_id(db_session), website="https://acme-switchgear.example.com/"
    )

    resp = await client.post("/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(lead.id)]})
    assert resp.status_code == 200, resp.text

    assert places_on == [], "Places must not be called when the lead already has a website"
    assert crawl == ["https://acme-switchgear.example.com/"]


@asyncio_test
async def test_without_google_places_the_lead_survives(
    client: AsyncClient, signed_up_user, db_session, crawl, places_off
):
    """Places is optional: no key must not fail the lead."""
    _, headers = signed_up_user
    lead = await _make_lead(db_session, await _org_id(db_session))

    resp = await client.post("/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(lead.id)]})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["discovery_available"] is False
    assert body["no_website"] == 1
    assert body["failed"] == 0, "a missing optional provider is not a failure"
    assert body["results"][0]["status"] == EnrichmentStatus.NO_WEBSITE_FOUND.value
    assert "not configured" in body["results"][0]["error"]


@asyncio_test
async def test_places_supplies_the_website_when_configured(
    client: AsyncClient, signed_up_user, db_session, crawl, places_on
):
    _, headers = signed_up_user
    lead = await _make_lead(db_session, await _org_id(db_session))

    resp = await client.post("/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(lead.id)]})
    body = resp.json()

    assert body["discovery_available"] is True
    assert body["website_found"] == 1
    result = body["results"][0]
    assert result["status"] == EnrichmentStatus.ENRICHED.value
    assert result["website_confidence"] and result["website_confidence"] >= 60


# --- Merging --------------------------------------------------------------


@asyncio_test
async def test_existing_contact_data_is_never_overwritten(
    client: AsyncClient, signed_up_user, db_session, crawl, places_off
):
    """A provider-supplied phone outranks one scraped from a footer."""
    _, headers = signed_up_user
    lead = await _make_lead(
        db_session,
        await _org_id(db_session),
        website="https://acme-switchgear.example.com/",
        phone="+919999900000",
    )
    lead_id = lead.id

    await client.post("/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(lead_id)]})

    db_session.expire_all()
    refreshed = (await db_session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one()
    assert refreshed.phone == "+919999900000", "the pre-existing phone must survive"
    # The empty field is still filled.
    assert refreshed.email == "sales@acme-switchgear.example.com"


@asyncio_test
async def test_gaps_are_filled_and_attributed(
    client: AsyncClient, signed_up_user, db_session, crawl, places_off
):
    _, headers = signed_up_user
    lead = await _make_lead(
        db_session, await _org_id(db_session), website="https://acme-switchgear.example.com/"
    )
    lead_id = lead.id

    resp = await client.post("/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(lead_id)]})
    sources = resp.json()["results"][0]["field_sources"]

    assert sources["phone"] == "https://acme-switchgear.example.com/contact"
    assert sources["email"] == "https://acme-switchgear.example.com/contact"
    assert sources["gst"] == "https://acme-switchgear.example.com/about"
    # Every provenance value must be a URL — the UI renders these as links.
    assert all(v.startswith("http") for v in sources.values()), sources


@asyncio_test
async def test_re_enriching_adds_nothing_and_stays_enriched(
    client: AsyncClient, signed_up_user, db_session, crawl, places_off
):
    _, headers = signed_up_user
    lead = await _make_lead(
        db_session, await _org_id(db_session), website="https://acme-switchgear.example.com/"
    )

    first = await client.post("/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(lead.id)]})
    second = await client.post("/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(lead.id)]})

    assert first.json()["results"][0]["fields_added"]
    assert second.json()["results"][0]["fields_added"] == []
    assert second.json()["results"][0]["status"] == EnrichmentStatus.ENRICHED.value


# --- Failure handling -----------------------------------------------------


@asyncio_test
async def test_an_unreachable_site_fails_only_that_lead(
    client: AsyncClient, signed_up_user, db_session, monkeypatch, places_off
):
    from services.enrichment import lead_enrichment

    async def failing_build(url, max_pages=None):
        return WebsiteProfile(url=url, domain="x", error="Connection refused")

    monkeypatch.setattr(lead_enrichment, "build_website_profile", failing_build)

    _, headers = signed_up_user
    org = await _org_id(db_session)
    bad = await _make_lead(db_session, org, name="Broken", website="https://broken.example.com/")
    good = await _make_lead(db_session, org, name="NoSite")

    resp = await client.post(
        "/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(bad.id), str(good.id)]}
    )
    body = resp.json()

    assert body["processed"] == 2, "the batch must not abort on one bad site"
    assert body["failed"] == 1
    assert body["no_website"] == 1


# --- Bulk -----------------------------------------------------------------


@asyncio_test
async def test_bulk_reports_every_counter(
    client: AsyncClient, signed_up_user, db_session, crawl, places_off
):
    _, headers = signed_up_user
    org = await _org_id(db_session)
    for i in range(3):
        await _make_lead(db_session, org, name=f"Acme {i}", website="https://acme-switchgear.example.com/")
    await _make_lead(db_session, org, name="No Site Co")

    resp = await client.post("/api/v1/leads/enrich", headers=headers, json={"all_unenriched": True})
    body = resp.json()

    assert body["total"] == 4
    assert body["processed"] == 4
    assert body["website_found"] == 3
    assert body["no_website"] == 1
    for key in ("phone_found", "email_found", "gst_found", "social_found", "failed"):
        assert key in body


@asyncio_test
async def test_enriching_nothing_is_rejected(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post("/api/v1/leads/enrich", headers=headers, json={"lead_ids": []})
    assert resp.status_code == 400


@asyncio_test
async def test_another_organizations_lead_is_not_enriched(
    client: AsyncClient, signed_up_user, crawl, places_off
):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(uuid.uuid4())]}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0, "a foreign id must select nothing"


@asyncio_test
async def test_enrichment_requires_authentication(client: AsyncClient):
    resp = await client.post("/api/v1/leads/enrich", json={"all_unenriched": True})
    assert resp.status_code in (401, 403)


# --- Credits --------------------------------------------------------------


@asyncio_test
async def test_no_outbound_work_means_no_charge(
    client: AsyncClient, signed_up_user, db_session, crawl, places_off
):
    """A lead with no provider and no website called nothing, so it costs nothing.

    Asserted on the settled charge the endpoint reports rather than on the wallet
    balance: the wallet needs a second read through the same async session, and
    expiring it mid-test triggers a lazy refresh outside the greenlet context.
    The settled figure is the contract anyway — it is what the ledger is written
    from.
    """
    _, headers = signed_up_user
    lead = await _make_lead(db_session, await _org_id(db_session), name="No Site Co")

    resp = await client.post(
        "/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(lead.id)]}
    )
    body = resp.json()

    assert body["no_website"] == 1
    assert body["credits_charged"] == 0


@asyncio_test
async def test_a_lead_that_did_work_is_charged(
    client: AsyncClient, signed_up_user, db_session, crawl, places_off
):
    """Positive control: without this, the test above passes on a broken meter."""
    _, headers = signed_up_user
    lead = await _make_lead(
        db_session, await _org_id(db_session), website="https://acme-switchgear.example.com/"
    )

    resp = await client.post(
        "/api/v1/leads/enrich", headers=headers, json={"lead_ids": [str(lead.id)]}
    )
    body = resp.json()

    assert body["website_found"] == 1
    assert body["credits_charged"] >= 1, "a crawl is outbound work and must be billed"
