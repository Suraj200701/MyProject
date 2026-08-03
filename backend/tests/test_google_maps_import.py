"""Google Maps Search module: URL building and importing an extractor CSV.

Scope note: LeadMaster never contacts Google Maps, so there is nothing to mock
here. The tests exercise URL construction and the CSV pipeline — which is all
the feature actually does.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from models.enums import ImportSource, ImportStatus
from models.lead import Company, Lead
from models.lead_import import LeadImport
from services import import_service
from services.enrichment.address import parse_address
from services.lead_import import parse_csv

# This module mixes sync (URL building, parsing, address) and async (API) tests.
# A module-level asyncio mark would make pytest-asyncio warn on every sync test,
# so async tests are marked individually — same approach as tests/test_url_guard.py.
asyncio_test = pytest.mark.asyncio(loop_scope="session")


# A realistic Google Maps Extractor export. Note what it has and hasn't: a
# formatted address but no city column, a "Category" instead of "Industry", a
# maps.google.com link alongside the real website, and no email at all.
MAPS_CSV = (
    b"Name,Full Address,Category,Phone,Website,Google Maps URL,Reviews,Rating,Business Status\n"
    b'Apple Foods,"Swami Vivekanand Road, Raipur, Ahmedabad, Gujarat, 380022",Restaurant,'
    b"+91 20 4567 8901,https://applefoods.example.com,"
    b"https://www.google.com/maps/place/?q=place_id:X1,142,4.6,OPERATIONAL\n"
    b'Lake Palace,"Lalshanker Road, Ahmedabad, Gujarat, 380022",Restaurant,,,'
    b"https://www.google.com/maps/place/?q=place_id:X2,88,4.1,OPERATIONAL\n"
)


# --- URL building ---------------------------------------------------------


def test_maps_url_matches_the_documented_search_form():
    url = import_service.build_maps_search_url("dentists", "Ahmedabad")
    assert url == "https://www.google.com/maps/search/dentists+Ahmedabad"


def test_maps_url_without_a_location():
    assert import_service.build_maps_search_url("dentists") == (
        "https://www.google.com/maps/search/dentists"
    )


def test_maps_url_escapes_user_input():
    """A keyword with punctuation must not break out of the path."""
    url = import_service.build_maps_search_url("caf&s / bars", "New Delhi")
    assert " " not in url
    assert "&" not in url.removeprefix(import_service.GOOGLE_MAPS_SEARCH_BASE)
    assert url.startswith(import_service.GOOGLE_MAPS_SEARCH_BASE)


def test_maps_url_requires_a_keyword():
    from utils.exceptions import BadRequestError

    with pytest.raises(BadRequestError):
        import_service.build_maps_search_url("   ")


@asyncio_test
async def test_search_url_endpoint(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/imports/google-maps/search-url",
        headers=headers,
        json={"keyword": "dentists", "location": "Ahmedabad"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "url": "https://www.google.com/maps/search/dentists+Ahmedabad",
        "keyword": "dentists",
        "location": "Ahmedabad",
    }


# --- Parsing an extractor export -----------------------------------------


def test_maps_export_columns_map_to_lead_fields():
    leads, errors, total = parse_csv(MAPS_CSV)

    assert (total, len(leads), len(errors)) == (2, 2, 0)
    first = leads[0]
    assert first.company_name == "Apple Foods"
    # "Category" is the industry in a Maps export.
    assert first.industry == "Restaurant"
    assert first.address == "Swami Vivekanand Road, Raipur, Ahmedabad, Gujarat, 380022"
    # No city column exists — it has to come from the address, or the lead would
    # be invisible to city filters and to dedup's city matching.
    assert first.city == "Ahmedabad"
    assert first.rating == 4.6
    assert first.phone == "+912045678901"
    assert first.raw["review_count"] == "142"
    assert first.raw["state"] == "Gujarat"
    assert first.raw["postal_code"] == "380022"


def test_a_maps_link_is_never_stored_as_the_company_website():
    """The bug this prevents: dedup matches on domain.

    If a `maps.google.com` link landed in `website`, every row in the export
    would share one domain and the whole import would collapse into a single
    company.
    """
    csv_bytes = (
        b"Name,Address,Website\n"
        b'Only A Maps Link,"MG Road, Bengaluru, Karnataka 560001, India",'
        b"https://maps.app.goo.gl/abc123\n"
    )
    leads, _errors, _total = parse_csv(csv_bytes)

    assert leads[0].website is None
    # Not discarded — kept where it belongs.
    assert leads[0].raw["maps_url"] == "https://maps.app.goo.gl/abc123"


def test_a_real_website_alongside_a_maps_link_survives():
    leads, _errors, _total = parse_csv(MAPS_CSV)
    assert leads[0].website == "https://applefoods.example.com"
    assert leads[0].raw["maps_url"] == "https://www.google.com/maps/place/?q=place_id:X1"


# --- Importing through the API -------------------------------------------


@asyncio_test
async def test_import_creates_leads_and_history(client: AsyncClient, signed_up_user, db_session):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/imports/google-maps",
        headers=headers,
        files={"file": ("maps-export.csv", MAPS_CSV, "text/csv")},
        data={"keyword": "restaurants", "location": "Ahmedabad"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["source"] == ImportSource.GOOGLE_MAPS_EXTRACTOR.value
    assert body["status"] == ImportStatus.COMPLETED.value
    assert body["total_rows"] == 2
    assert body["imported"] == 2
    assert body["invalid_rows"] == 0
    # The search context is what makes a run recognisable later.
    assert body["keyword"] == "restaurants"
    assert body["location"] == "Ahmedabad"
    assert body["file_name"] == "maps-export.csv"
    assert body["completed_at"] is not None

    companies = (
        await db_session.execute(select(Company).where(Company.name == "Apple Foods"))
    ).scalars().all()
    assert len(companies) == 1
    # The address must be persisted, not parsed and thrown away.
    assert companies[0].address == "Swami Vivekanand Road, Raipur, Ahmedabad, Gujarat, 380022"
    assert companies[0].city == "Ahmedabad"


@asyncio_test
async def test_imported_leads_are_scored(client: AsyncClient, signed_up_user, db_session):
    _, headers = signed_up_user
    await client.post(
        "/api/v1/imports/google-maps",
        headers=headers,
        files={"file": ("m.csv", MAPS_CSV, "text/csv")},
        data={"keyword": "restaurants", "location": "Ahmedabad"},
    )
    leads = (await db_session.execute(select(Lead))).scalars().all()
    assert len(leads) == 2
    assert all(lead.lead_score > 0 for lead in leads), "the scorer must run on imports"


@asyncio_test
async def test_re_importing_the_same_export_is_deduplicated(
    client: AsyncClient, signed_up_user, db_session
):
    """Users re-export after scrolling further; the overlap must not double up."""
    _, headers = signed_up_user
    files = {"file": ("m.csv", MAPS_CSV, "text/csv")}
    data = {"keyword": "restaurants", "location": "Ahmedabad"}

    first = await client.post("/api/v1/imports/google-maps", headers=headers, files=files, data=data)
    assert first.json()["imported"] == 2

    second = await client.post(
        "/api/v1/imports/google-maps",
        headers=headers,
        files={"file": ("m.csv", MAPS_CSV, "text/csv")},
        data=data,
    )
    body = second.json()
    assert body["imported"] == 0
    assert body["duplicates_skipped"] == 2
    # Nothing imported is not the same as success.
    assert body["status"] == ImportStatus.COMPLETED_EMPTY.value

    leads = (await db_session.execute(select(Lead))).scalars().all()
    assert len(leads) == 2, "a re-import must not duplicate leads"


@asyncio_test
async def test_a_rejected_file_is_recorded_as_failed(
    client: AsyncClient, signed_up_user, db_session
):
    """A 400 must still leave evidence — not a row stuck in PROCESSING."""
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/imports/google-maps",
        headers=headers,
        files={"file": ("bad.csv", b"Rating,Reviews\n4.5,10\n", "text/csv")},
        data={"keyword": "x"},
    )
    assert resp.status_code == 400
    assert "company name" in resp.json()["message"]

    db_session.expire_all()
    record = (
        await db_session.execute(select(LeadImport).order_by(LeadImport.created_at.desc()))
    ).scalars().first()
    assert record is not None
    assert record.status is ImportStatus.FAILED
    assert "company name" in record.error_message
    assert record.completed_at is not None


@asyncio_test
async def test_per_row_errors_are_reported_and_capped(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    rows = b"Name,Address,GSTIN\n"
    rows += b"".join(
        f'Co {i},"MG Road, Pune, Maharashtra 411001",NOTAVALIDGSTIN\n'.encode() for i in range(3)
    )
    resp = await client.post(
        "/api/v1/imports/google-maps",
        headers=headers,
        files={"file": ("m.csv", rows, "text/csv")},
        data={"keyword": "x"},
    )
    body = resp.json()
    # A bad GSTIN reports the row but still imports the lead without it.
    assert body["imported"] == 3
    assert len(body["row_errors"]) == 3
    assert all("GSTIN" in e["message"] for e in body["row_errors"])


@asyncio_test
async def test_empty_file_is_rejected(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/imports/google-maps",
        headers=headers,
        files={"file": ("empty.csv", b"   ", "text/csv")},
        data={"keyword": "x"},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["message"].lower()


# --- History --------------------------------------------------------------


@asyncio_test
async def test_history_lists_newest_first_and_filters_by_source(
    client: AsyncClient, signed_up_user
):
    _, headers = signed_up_user
    await client.post(
        "/api/v1/imports/google-maps",
        headers=headers,
        files={"file": ("a.csv", MAPS_CSV, "text/csv")},
        data={"keyword": "restaurants", "location": "Ahmedabad"},
    )
    await client.post(
        "/api/v1/imports",
        headers=headers,
        files={"file": ("b.csv", b"Company,City\nPlain Co,Pune\n", "text/csv")},
    )

    listing = await client.get("/api/v1/imports", headers=headers)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 2
    assert items[0]["file_name"] == "b.csv", "newest first"

    filtered = await client.get(
        "/api/v1/imports",
        headers=headers,
        params={"source": ImportSource.GOOGLE_MAPS_EXTRACTOR.value},
    )
    filtered_items = filtered.json()["items"]
    assert len(filtered_items) == 1
    assert filtered_items[0]["file_name"] == "a.csv"


@asyncio_test
async def test_import_detail_is_scoped_to_the_organization(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    created = await client.post(
        "/api/v1/imports/google-maps",
        headers=headers,
        files={"file": ("a.csv", MAPS_CSV, "text/csv")},
        data={"keyword": "x"},
    )
    import_id = created.json()["id"]

    mine = await client.get(f"/api/v1/imports/{import_id}", headers=headers)
    assert mine.status_code == 200
    assert mine.json()["id"] == import_id

    missing = await client.get(f"/api/v1/imports/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404


@asyncio_test
async def test_import_endpoints_require_authentication(client: AsyncClient):
    assert (await client.get("/api/v1/imports")).status_code in (401, 403)
    assert (
        await client.post(
            "/api/v1/imports/google-maps/search-url", json={"keyword": "x"}
        )
    ).status_code in (401, 403)


# --- Address parsing (shared with the Mappls adapter) --------------------


@pytest.mark.parametrize(
    ("address", "city", "state", "postal"),
    [
        ("Swami Vivekanand Road, Raipur, Ahmedabad, Gujarat, 380022", "Ahmedabad", "Gujarat", "380022"),
        ("MG Road, Indiranagar, Bengaluru, Karnataka 560001, India", "Bengaluru", "Karnataka", "560001"),
        ("123 Main St, Springfield, IL 62704, USA", "Springfield", "IL", "62704"),
        # Two components are ambiguous; the trailing one is taken as the city.
        ("Wagle Estate, Thane", "Thane", None, None),
        # A lone administrative name must not become a city.
        ("Gujarat", None, "Gujarat", None),
        ("", None, None, None),
    ],
)
def test_address_parsing(address, city, state, postal):
    parsed = parse_address(address)
    assert (parsed.city, parsed.state, parsed.postal_code) == (city, state, postal)
