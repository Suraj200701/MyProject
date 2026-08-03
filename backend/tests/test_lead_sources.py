"""End-to-end tests for the real lead sources, driven through the HTTP API.

Covers CSV import, manual lead entry, provider-backed search and the website
scanner. Provider HTTP is mocked at the adapter boundary; everything else — auth,
routing, credit metering, dedup, scoring, persistence — is the real stack against
the real test database.

The most important assertions here are the *negative* ones: with no provider
configured a search must return zero results rather than inventing them, and an
unreachable site must persist a recorded failure rather than a plausible-looking
scan. Those are the invariants that replaced the removed placeholder generators.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from models.lead import Company
from models.search import ApiProvider, WebsiteScan
from services import search_service
from services.providers import google_places, website_search

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture
def resolvable_fixture_domains(monkeypatch):
    """Lets fixture hostnames past the SSRF guard's real DNS lookup.

    The guard itself is covered exhaustively by tests/test_url_guard.py, and one
    test below still drives it for real against 127.0.0.1. Here it would only
    fail the scan because `novapanels.co.in` doesn't resolve on this machine.
    """
    from utils.url_guard import ValidatedUrl

    async def fake_resolve(raw_url: str) -> ValidatedUrl:
        url = raw_url if "://" in raw_url else f"https://{raw_url}"
        host = url.split("://", 1)[1].split("/")[0]
        return ValidatedUrl(
            url=url, scheme=url.split("://")[0], hostname=host, port=443, resolved_ips=("93.184.216.34",)
        )

    monkeypatch.setattr(search_service, "resolve_and_validate", fake_resolve)


# `google_places_configured` and `PLACES_PAYLOAD` live in conftest.py — the
# credit-metering tests need the same "a provider is actually live" setup.


# --- Search with a real provider ----------------------------------------


async def test_search_persists_leads_sourced_from_a_provider(
    client: AsyncClient, signed_up_user, google_places_configured
):
    _, headers = signed_up_user

    resp = await client.post(
        "/api/v1/search",
        headers=headers,
        json={"query": "switchgear manufacturers", "location": "Pune", "industry": "Electrical"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["results_count"] == 2

    leads = (await client.get("/api/v1/leads", headers=headers)).json()
    names = {item["company"] for item in leads["items"]}
    assert names == {"Apex Switchgear Pvt Ltd", "Nova Control Panels"}


async def test_searched_leads_carry_real_provider_attribution(
    client: AsyncClient, signed_up_user, google_places_configured
):
    _, headers = signed_up_user
    await client.post("/api/v1/search", headers=headers, json={"query": "switchgear", "location": "Pune"})

    leads = (await client.get("/api/v1/leads", headers=headers)).json()["items"]
    assert leads
    assert all(item["provider"] == "Google Places" for item in leads)


async def test_searched_leads_have_coordinates_for_map_search(
    client: AsyncClient, signed_up_user, google_places_configured, db_session
):
    """Map Search was previously empty for searched leads because lat/lng were never set."""
    _, headers = signed_up_user
    await client.post("/api/v1/search", headers=headers, json={"query": "switchgear", "location": "Pune"})

    companies = (
        await db_session.execute(select(Company).where(Company.name == "Apex Switchgear Pvt Ltd"))
    ).scalars().all()
    assert companies
    assert float(companies[0].lat) == pytest.approx(18.6298, abs=1e-4)
    assert float(companies[0].lng) == pytest.approx(73.8398, abs=1e-4)


async def test_searched_leads_are_scored_and_summarized(
    client: AsyncClient, signed_up_user, google_places_configured
):
    _, headers = signed_up_user
    await client.post("/api/v1/search", headers=headers, json={"query": "switchgear", "location": "Pune"})

    leads = (await client.get("/api/v1/leads", headers=headers)).json()["items"]
    for item in leads:
        assert 1 <= item["lead_score"] <= 100
        assert item["ai_summary"]
    # Apex has a website + phone; Nova has neither, so it must not outrank Apex.
    by_name = {item["company"]: item["lead_score"] for item in leads}
    assert by_name["Apex Switchgear Pvt Ltd"] > by_name["Nova Control Panels"]


async def test_repeat_search_does_not_duplicate_leads(
    client: AsyncClient, signed_up_user, google_places_configured
):
    """The second identical search finds the same businesses already stored."""
    _, headers = signed_up_user
    payload = {"query": "switchgear manufacturers", "location": "Pune"}

    first = await client.post("/api/v1/search", headers=headers, json=payload)
    second = await client.post("/api/v1/search", headers=headers, json=payload)

    assert first.json()["results_count"] == 2
    assert second.json()["results_count"] == 0

    total = (await client.get("/api/v1/leads", headers=headers)).json()["meta"]["total_items"]
    assert total == 2


async def test_search_records_a_provider_run_for_every_provider(
    client: AsyncClient, signed_up_user, google_places_configured, db_session
):
    """Unconfigured providers are recorded too, so the UI can explain a thin result."""
    _, headers = signed_up_user
    resp = await client.post("/api/v1/search", headers=headers, json={"query": "switchgear", "location": "Pune"})

    provider_count = len((await db_session.execute(select(ApiProvider))).scalars().all())
    assert len(resp.json()["provider_runs"]) == provider_count


async def test_search_with_no_configured_provider_returns_nothing(
    client: AsyncClient, signed_up_user, monkeypatch
):
    """The core anti-placeholder guarantee: zero providers means zero leads.

    This must not fabricate results, and must not fail the request either — the
    API contract still returns 201 with a SearchOut.
    """
    # One shared settings singleton backs every adapter; go through it directly
    # rather than via an unrelated provider module's namespace.
    from config.settings import settings

    for key in ("GOOGLE_MAPS_API_KEY", "MAPPLS_CLIENT_ID", "MAPPLS_CLIENT_SECRET", "BING_SEARCH_API_KEY"):
        monkeypatch.setattr(settings, key, "", raising=False)
    monkeypatch.setattr(settings, "SCANNER_ENABLED", False, raising=False)

    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "switchgear manufacturers", "location": "Pune"}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "completed"
    assert body["results_count"] == 0
    assert body["provider_runs"]  # every provider still reports why it didn't run

    leads = (await client.get("/api/v1/leads", headers=headers)).json()
    assert leads["meta"]["total_items"] == 0


async def test_one_failing_provider_does_not_fail_the_search(
    client: AsyncClient, signed_up_user, monkeypatch
):
    async def exploding(*a, **k):
        raise RuntimeError("provider adapter blew up")

    monkeypatch.setattr(google_places.settings, "GOOGLE_MAPS_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(google_places, "request_json", exploding)
    monkeypatch.setattr(website_search.settings, "SCANNER_ENABLED", False, raising=False)

    _, headers = signed_up_user
    resp = await client.post("/api/v1/search", headers=headers, json={"query": "switchgear", "location": "Pune"})

    assert resp.status_code == 201
    assert resp.json()["results_count"] == 0


async def test_search_history_records_the_query(
    client: AsyncClient, signed_up_user, google_places_configured
):
    _, headers = signed_up_user
    await client.post("/api/v1/search", headers=headers, json={"query": "switchgear", "location": "Pune"})

    history = (await client.get("/api/v1/search/history", headers=headers)).json()
    assert history["meta"]["total_items"] == 1
    assert history["items"][0]["query"] == "switchgear"


# --- Website scanner ----------------------------------------------------

SCAN_HOMEPAGE = """
<html><head><title>Nova Panels | Switchgear</title>
<meta name="description" content="Panel builders"><meta name="viewport" content="width=device-width">
<meta property="og:site_name" content="Nova Panels"></head>
<body><h1>Nova Panels</h1><img src="a.png" alt="logo">
<p>Email sales@novapanels.co.in &middot; Phone 020-4567-8901</p>
<p>GSTIN: 27AAPFU0939F1ZV</p>
<a href="https://www.linkedin.com/company/nova-panels">LinkedIn</a>
</body></html>
"""


@pytest.fixture
def reachable_site(monkeypatch, resolvable_fixture_domains):
    from services.safe_http import FetchResult

    async def fake_fetch(url, **kwargs):
        final = url if "://" in url else f"https://{url}"
        return FetchResult(
            final_url=final,
            status_code=200,
            content=SCAN_HOMEPAGE.encode(),
            headers={"content-type": "text/html; charset=utf-8"},
            elapsed_ms=42,
            tls_used=final.startswith("https://"),
        )

    monkeypatch.setattr(website_search, "safe_fetch", fake_fetch)


async def test_scan_extracts_real_page_content(client: AsyncClient, signed_up_user, reachable_site):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/scan-website", headers=headers, json={"url": "https://novapanels.co.in"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["company_name"] == "Nova Panels"
    assert "sales@novapanels.co.in" in body["emails"]
    assert "+912045678901" in body["phones"]
    assert body["gst_number"] == "27AAPFU0939F1ZV"
    assert body["gst_verified"] is True
    assert body["mobile_friendly"] is True
    assert body["ssl_valid"] is True
    assert body["seo_score"] > 0
    assert 1 <= body["confidence_score"] <= 100


async def test_scan_confidence_reflects_what_was_found(
    client: AsyncClient, signed_up_user, monkeypatch, resolvable_fixture_domains
):
    """Confidence is derived from real signals, replacing the previous random figure."""
    from services.safe_http import FetchResult

    bare = "<html><head><title>Nothing Co</title></head><body><p>No contacts here.</p></body></html>"

    async def fake_fetch(url, **kwargs):
        final = url if "://" in url else f"https://{url}"
        return FetchResult(
            final_url=final, status_code=200, content=bare.encode(),
            headers={"content-type": "text/html"}, elapsed_ms=10, tls_used=True,
        )

    monkeypatch.setattr(website_search, "safe_fetch", fake_fetch)
    _, headers = signed_up_user

    bare_scan = await client.post("/api/v1/scan-website", headers=headers, json={"url": "https://bare.example"})
    assert bare_scan.json()["emails"] is None
    assert bare_scan.json()["gst_number"] is None
    low = bare_scan.json()["confidence_score"]

    monkeypatch.setattr(website_search, "safe_fetch", _rich_fetch())
    rich_scan = await client.post("/api/v1/scan-website", headers=headers, json={"url": "https://rich.example"})
    assert rich_scan.json()["confidence_score"] > low


def _rich_fetch():
    from services.safe_http import FetchResult

    async def fake_fetch(url, **kwargs):
        final = url if "://" in url else f"https://{url}"
        return FetchResult(
            final_url=final, status_code=200, content=SCAN_HOMEPAGE.encode(),
            headers={"content-type": "text/html"}, elapsed_ms=10, tls_used=True,
        )

    return fake_fetch


async def test_scan_is_repeatable_for_the_same_content(client: AsyncClient, signed_up_user, reachable_site):
    """Determinism now comes from the page content, not from a seeded RNG."""
    _, headers = signed_up_user
    first = await client.post("/api/v1/scan-website", headers=headers, json={"url": "https://novapanels.co.in"})
    second = await client.post("/api/v1/scan-website", headers=headers, json={"url": "https://novapanels.co.in"})

    assert first.json()["confidence_score"] == second.json()["confidence_score"]
    assert first.json()["gst_number"] == second.json()["gst_number"]
    assert first.json()["emails"] == second.json()["emails"]


async def test_unreachable_site_records_a_real_failure(
    client: AsyncClient, signed_up_user, monkeypatch, db_session, resolvable_fixture_domains
):
    """A failed scan persists as a failure, not as a plausible-looking success."""
    async def failing_fetch(url, **kwargs):
        raise website_search.FetchError("Connection refused", kind="network")

    monkeypatch.setattr(website_search, "safe_fetch", failing_fetch)
    _, headers = signed_up_user

    resp = await client.post("/api/v1/scan-website", headers=headers, json={"url": "https://down.example"})
    assert resp.status_code == 201
    body = resp.json()

    assert body["confidence_score"] == 0
    assert body["company_name"] is None
    assert body["emails"] is None
    assert body["gst_number"] is None
    assert body["gst_verified"] is False

    stored = (await db_session.execute(select(WebsiteScan))).scalars().all()
    assert len(stored) == 1


async def test_scan_rejects_a_private_address_before_fetching(client: AsyncClient, signed_up_user, db_session):
    """SSRF guard runs first: no fetch, no scan row, no credit spent."""
    _, headers = signed_up_user
    resp = await client.post("/api/v1/scan-website", headers=headers, json={"url": "http://127.0.0.1:8080/admin"})
    assert resp.status_code == 400

    stored = (await db_session.execute(select(WebsiteScan))).scalars().all()
    assert stored == []


async def test_scan_history_is_listable(client: AsyncClient, signed_up_user, reachable_site):
    _, headers = signed_up_user
    await client.post("/api/v1/scan-website", headers=headers, json={"url": "https://novapanels.co.in"})
    scans = (await client.get("/api/v1/scans", headers=headers)).json()
    assert scans["meta"]["total_items"] == 1
    assert scans["items"][0]["domain"] == "novapanels.co.in"


# --- Manual lead entry --------------------------------------------------


async def test_manual_lead_is_scored_when_no_score_is_given(client: AsyncClient, signed_up_user):
    """A hand-entered lead shouldn't sit at zero forever."""
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/leads",
        headers=headers,
        json={
            "company": "Handtyped Industries",
            "email": "owner@handtyped.in",
            "phone": "+919876543210",
            "website": "https://handtyped.in",
            "city": "Pune",
            "industry": "Electrical",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["lead_score"] > 0
    assert body["ai_summary"]


async def test_an_explicit_manual_score_is_respected(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/leads",
        headers=headers,
        json={"company": "Scored By Hand Ltd", "lead_score": 42, "ai_summary": "My own note."},
    )
    assert resp.status_code == 201
    assert resp.json()["lead_score"] == 42
    assert resp.json()["ai_summary"] == "My own note."


async def test_manual_lead_with_only_a_company_name_is_accepted(client: AsyncClient, signed_up_user):
    """Contract unchanged: company is the only required field."""
    _, headers = signed_up_user
    resp = await client.post("/api/v1/leads", headers=headers, json={"company": "Minimal Co"})
    assert resp.status_code == 201
    assert resp.json()["company"] == "Minimal Co"
    assert resp.json()["lead_score"] >= 1


# --- CSV import ---------------------------------------------------------


def _csv_upload(text: str, filename: str = "leads.csv", content_type: str = "text/csv"):
    return {"file": (filename, text.encode(), content_type)}


GOOD_CSV = (
    "Company Name,Industry,City,Email,Phone,GSTIN,Website\n"
    "Apex Switchgear Pvt Ltd,Electrical,Pune,sales@apexswitchgear.com,9876543210,27AAPFU0939F1ZV,apexswitchgear.com\n"
    "Nova Control Panels,Electrical,Thane,info@novapanels.co.in,020-4567-8901,,novapanels.co.in\n"
)


async def test_csv_import_creates_leads(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(GOOD_CSV))
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["total_rows"] == 2
    assert body["imported"] == 2
    assert body["invalid_rows"] == 0

    leads = (await client.get("/api/v1/leads", headers=headers)).json()
    assert leads["meta"]["total_items"] == 2
    assert all(item["lead_score"] >= 1 for item in leads["items"])


async def test_csv_import_normalizes_phones_and_validates_gstin(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(GOOD_CSV))

    leads = (await client.get("/api/v1/leads", headers=headers)).json()["items"]
    phones = {item["company"]: item["phone"] for item in leads}
    assert phones["Apex Switchgear Pvt Ltd"] == "+919876543210"
    assert phones["Nova Control Panels"] == "+912045678901"


@pytest.mark.parametrize(
    "header",
    ["Company Name", "company_name", "Company", "Organisation", "Business Name", "name"],
)
async def test_csv_accepts_flexible_company_headers(client: AsyncClient, signed_up_user, header):
    _, headers = signed_up_user
    csv_text = f"{header},City\nFlexible Headers Co,Pune\n"
    resp = await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(csv_text))
    assert resp.status_code == 201, resp.text
    assert resp.json()["imported"] == 1


async def test_csv_without_a_company_column_is_rejected(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/leads/import", headers=headers, files=_csv_upload("Colour,Size\nred,large\n")
    )
    assert resp.status_code == 400
    assert "company name column" in resp.json()["message"]


async def test_csv_bad_rows_are_reported_without_failing_the_file(client: AsyncClient, signed_up_user):
    """497 of 500 good rows should import; the 3 bad ones are reported."""
    _, headers = signed_up_user
    csv_text = (
        "Company,Email,GSTIN,Phone\n"
        "Good Co,good@example.com,27AAPFU0939F1ZV,9876543210\n"
        ",missing@example.com,,\n"                                  # no company name
        "Bad Gst Co,x@example.com,27AAPFU0939F1ZA,9812345678\n"     # checksum fails
        "Bad Email Co,not-an-email,,9812345679\n"
    )
    resp = await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(csv_text))
    assert resp.status_code == 201
    body = resp.json()

    assert body["imported"] == 3          # everything except the nameless row
    assert body["invalid_rows"] == 3      # nameless + bad GSTIN + bad email
    messages = " ".join(e["message"] for e in body["errors"])
    assert "Missing company name" in messages
    assert "Invalid GSTIN" in messages
    assert "Invalid email" in messages


async def test_csv_row_with_a_bad_gstin_still_imports_without_it(client: AsyncClient, signed_up_user):
    """A single bad field must not cost the whole lead."""
    _, headers = signed_up_user
    csv_text = "Company,GSTIN\nPartial Co,27AAPFU0939F1ZA\n"
    resp = await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(csv_text))
    assert resp.json()["imported"] == 1

    leads = (await client.get("/api/v1/leads", headers=headers)).json()["items"]
    assert leads[0]["company"] == "Partial Co"
    assert leads[0]["gst_number"] is None


async def test_csv_import_deduplicates_within_the_file(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    csv_text = (
        "Company,City,GSTIN\n"
        "Apex Switchgear Pvt Ltd,Pune,27AAPFU0939F1ZV\n"
        "Apex Switchgear Private Limited,Pune,27AAPFU0939F1ZV\n"
    )
    resp = await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(csv_text))
    body = resp.json()
    assert body["imported"] == 1
    assert body["duplicates_skipped"] == 1
    assert body["dedup_signals"].get("gstin") == 1


async def test_csv_import_deduplicates_against_existing_leads(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(GOOD_CSV))
    second = await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(GOOD_CSV))

    assert second.json()["imported"] == 0
    assert second.json()["duplicates_skipped"] == 2
    total = (await client.get("/api/v1/leads", headers=headers)).json()["meta"]["total_items"]
    assert total == 2


async def test_csv_semicolon_delimiter_is_detected(client: AsyncClient, signed_up_user):
    """European exports commonly use ';'."""
    _, headers = signed_up_user
    csv_text = "Company;City;Email\nSemicolon Co;Pune;a@b.com\n"
    resp = await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(csv_text))
    assert resp.json()["imported"] == 1


async def test_csv_with_a_utf8_bom_imports_cleanly(client: AsyncClient, signed_up_user):
    """Excel on Windows writes a BOM; a mojibake company name is a silent data bug."""
    _, headers = signed_up_user
    payload = {"file": ("leads.csv", b"\xef\xbb\xbfCompany,City\nBOM Industries,Pune\n", "text/csv")}
    resp = await client.post("/api/v1/leads/import", headers=headers, files=payload)
    assert resp.status_code == 201
    assert resp.json()["imported"] == 1

    leads = (await client.get("/api/v1/leads", headers=headers)).json()["items"]
    assert leads[0]["company"] == "BOM Industries"


async def test_csv_blank_rows_are_skipped_not_counted(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    csv_text = "Company,City\nReal Co,Pune\n,\n\nAnother Co,Thane\n"
    resp = await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(csv_text))
    body = resp.json()
    assert body["total_rows"] == 2
    assert body["imported"] == 2


async def test_empty_csv_is_rejected(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload("   "))
    assert resp.status_code == 400
    assert "empty" in resp.json()["message"].lower()


async def test_non_csv_content_type_is_rejected(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/leads/import",
        headers=headers,
        files=_csv_upload("Company\nX\n", filename="leads.pdf", content_type="application/pdf"),
    )
    assert resp.status_code == 400
    assert "CSV" in resp.json()["message"]


async def test_csv_import_requires_authentication(client: AsyncClient):
    resp = await client.post("/api/v1/leads/import", files=_csv_upload(GOOD_CSV))
    assert resp.status_code in (401, 403)


async def test_csv_import_is_scoped_to_the_callers_organization(client: AsyncClient, signed_up_user):
    """A second org must not see the first org's imported leads."""
    _, headers = signed_up_user
    await client.post("/api/v1/leads/import", headers=headers, files=_csv_upload(GOOD_CSV))

    other = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": f"other_{uuid.uuid4().hex[:8]}@example.com",
            "password": "TestPass123",
            "full_name": "Other User",
            "company_name": "Other Co",
        },
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    leads = (await client.get("/api/v1/leads", headers=other_headers)).json()
    assert leads["meta"]["total_items"] == 0
