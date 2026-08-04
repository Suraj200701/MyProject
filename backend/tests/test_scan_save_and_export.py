"""Saving a website scan as a lead, and exporting scans.

Both actions were UI-only: the buttons fired `toast.success(...)` and did
nothing, so scan findings could be neither saved nor exported. These tests pin
the real behaviour.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from models.enums import ExportResource
from models.lead import Lead
from models.search import WebsiteScan
from services import export_datasets

# Mixed sync/async module — a module-level mark makes pytest-asyncio warn on
# every sync test, so async tests are marked individually.
asyncio_test = pytest.mark.asyncio(loop_scope="session")


async def _make_scan(db_session, organization_id, **overrides) -> WebsiteScan:
    fields = dict(
        organization_id=organization_id,
        url="https://apexswitchgear.example.com",
        domain="apexswitchgear.example.com",
        company_name="Apex Switchgear",
        contact_person="R. Mehta",
        confidence_score=82,
        emails=["sales@apexswitchgear.example.com", "info@apexswitchgear.example.com"],
        phones=["+912045678901", "+919825011111"],
        gst_number="24AAACC1206D1ZM",
        gst_verified=True,
        social_links={"linkedin": "https://linkedin.com/company/apex"},
        ssl_valid=True,
        mobile_friendly=True,
        load_time_ms=850,
        seo_score=71,
        scan_duration_ms=2400,
    )
    # Overrides replace the defaults rather than being passed alongside them.
    fields.update(overrides)
    scan = WebsiteScan(**fields)
    db_session.add(scan)
    await db_session.commit()
    await db_session.refresh(scan)
    return scan


async def _org_id(db_session) -> uuid.UUID:
    from models.organization import Organization

    stmt = select(Organization).order_by(Organization.created_at.desc()).limit(1)
    return (await db_session.execute(stmt)).scalar_one().id


# --- Save to Lead ---------------------------------------------------------


@asyncio_test
async def test_scan_is_saved_as_a_real_lead(client: AsyncClient, signed_up_user, db_session):
    _, headers = signed_up_user
    org_id = await _org_id(db_session)
    scan = await _make_scan(db_session, org_id)

    resp = await client.post(f"/api/v1/scans/{scan.id}/save-lead", headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["company"] == "Apex Switchgear"
    assert body["website"] == "https://apexswitchgear.example.com"
    # First of each multi-valued field lands on the lead; all of them stay on the
    # scan and reach the export.
    assert body["email"] == "sales@apexswitchgear.example.com"
    assert body["phone"] == "+912045678901"
    assert body["contact_name"] == "R. Mehta"
    # A verified GSTIN carries over; scoring runs for real.
    assert body["gst_number"] == "24AAACC1206D1ZM"
    assert body["lead_score"] > 0

    lead = (await db_session.execute(select(Lead).where(Lead.id == uuid.UUID(body["id"])))).scalar_one()
    assert lead.organization_id == org_id


@asyncio_test
async def test_saving_links_the_scan_to_the_lead(client: AsyncClient, signed_up_user, db_session):
    """`WebsiteScan.lead_id` existed for this and was never written."""
    _, headers = signed_up_user
    scan = await _make_scan(db_session, await _org_id(db_session))
    scan_id = scan.id

    before = (
        await db_session.execute(select(WebsiteScan.lead_id).where(WebsiteScan.id == scan_id))
    ).scalar_one()
    assert before is None

    resp = await client.post(f"/api/v1/scans/{scan_id}/save-lead", headers=headers)

    db_session.expire_all()
    refreshed = (
        await db_session.execute(select(WebsiteScan).where(WebsiteScan.id == scan_id))
    ).scalar_one()
    assert refreshed.lead_id is not None
    assert str(refreshed.lead_id) == resp.json()["id"]


@asyncio_test
async def test_saving_twice_does_not_create_two_leads(
    client: AsyncClient, signed_up_user, db_session
):
    """Clicking the button again must be a no-op, not a duplicate."""
    _, headers = signed_up_user
    scan = await _make_scan(db_session, await _org_id(db_session))

    first = await client.post(f"/api/v1/scans/{scan.id}/save-lead", headers=headers)
    second = await client.post(f"/api/v1/scans/{scan.id}/save-lead", headers=headers)

    assert first.status_code == 201
    # Nothing was created the second time, so 201 would be a lie.
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    leads = (await db_session.execute(select(Lead))).scalars().all()
    assert len(leads) == 1


@asyncio_test
async def test_a_scan_of_an_existing_company_links_instead_of_duplicating(
    client: AsyncClient, signed_up_user, db_session
):
    """Dedup runs, so scanning a company you already have does not double it up."""
    _, headers = signed_up_user
    org_id = await _org_id(db_session)

    first_scan = await _make_scan(db_session, org_id)
    first = await client.post(f"/api/v1/scans/{first_scan.id}/save-lead", headers=headers)
    assert first.status_code == 201

    # A second scan of the same domain — the dedup domain signal should match.
    second_scan = await _make_scan(db_session, org_id, company_name="Apex Switchgear Pvt Ltd")
    second_scan_id = second_scan.id
    second = await client.post(f"/api/v1/scans/{second_scan_id}/save-lead", headers=headers)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    leads = (await db_session.execute(select(Lead))).scalars().all()
    assert len(leads) == 1, "the same company must not be stored twice"

    db_session.expire_all()
    refreshed = (
        await db_session.execute(select(WebsiteScan).where(WebsiteScan.id == second_scan_id))
    ).scalar_one()
    # The second scan is still linked, so the UI can show what it resolved to.
    assert str(refreshed.lead_id) == first.json()["id"]


@asyncio_test
async def test_a_scan_with_nothing_usable_is_rejected(
    client: AsyncClient, signed_up_user, db_session
):
    _, headers = signed_up_user
    scan = WebsiteScan(
        organization_id=await _org_id(db_session),
        url="https://nothing.example.com",
        domain="",
        company_name=None,
        confidence_score=0,
        scan_duration_ms=100,
    )
    db_session.add(scan)
    await db_session.commit()
    await db_session.refresh(scan)

    resp = await client.post(f"/api/v1/scans/{scan.id}/save-lead", headers=headers)
    assert resp.status_code == 400
    assert "nothing to save" in resp.json()["message"]


@asyncio_test
async def test_another_organizations_scan_is_not_saveable(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post(f"/api/v1/scans/{uuid.uuid4()}/save-lead", headers=headers)
    assert resp.status_code == 404


@asyncio_test
async def test_save_lead_requires_authentication(client: AsyncClient):
    resp = await client.post(f"/api/v1/scans/{uuid.uuid4()}/save-lead")
    assert resp.status_code in (401, 403)


# --- Exporting scans ------------------------------------------------------


@asyncio_test
async def test_website_scans_is_an_exportable_resource(
    client: AsyncClient, signed_up_user, db_session
):
    _, headers = signed_up_user
    await _make_scan(db_session, await _org_id(db_session))

    resp = await client.post(
        "/api/v1/exports",
        headers=headers,
        json={"resource": "website_scans", "format": "csv"},
    )
    assert resp.status_code in (201, 202), resp.text
    assert resp.json()["resource"] == ExportResource.WEBSITE_SCANS.value


@asyncio_test
async def test_exporting_one_scan_contains_its_findings(
    client: AsyncClient, signed_up_user, db_session
):
    """The whole point: every email/phone the scan found, not just the first."""
    _, headers = signed_up_user
    scan = await _make_scan(db_session, await _org_id(db_session))

    created = await client.post(
        "/api/v1/exports",
        headers=headers,
        json={"resource": "website_scans", "format": "csv", "scan_id": str(scan.id)},
    )
    assert created.status_code == 201, created.text
    export_id = created.json()["id"]

    token = (await client.post(f"/api/v1/exports/{export_id}/download-token", headers=headers)).json()
    download = await client.get(
        f"/api/v1/exports/{export_id}/download", params={"token": token["token"]}
    )
    assert download.status_code == 200
    text = download.content.decode("utf-8-sig")

    assert "Apex Switchgear" in text
    assert "apexswitchgear.example.com" in text
    # Both addresses and both numbers, which no single lead field could hold.
    assert "sales@apexswitchgear.example.com" in text
    assert "info@apexswitchgear.example.com" in text
    assert "+919825011111" in text
    assert "24AAACC1206D1ZM" in text
    assert "linkedin" in text


@asyncio_test
async def test_scan_export_uses_scan_columns_not_lead_columns(
    client: AsyncClient, signed_up_user, db_session
):
    """A resource falling through to LEAD_COLUMNS produced an all-empty file."""
    _, headers = signed_up_user
    scan = await _make_scan(db_session, await _org_id(db_session))

    created = await client.post(
        "/api/v1/exports",
        headers=headers,
        json={"resource": "website_scans", "format": "csv", "scan_id": str(scan.id)},
    )
    token = (
        await client.post(f"/api/v1/exports/{created.json()['id']}/download-token", headers=headers)
    ).json()
    text = (
        await client.get(
            f"/api/v1/exports/{created.json()['id']}/download", params={"token": token["token"]}
        )
    ).content.decode("utf-8-sig")

    # Every export begins with a title/metadata preamble; the column header is
    # the first line that actually carries the column names.
    header = next(line for line in text.splitlines() if line.startswith("Company,"))
    assert "Confidence" in header
    assert "SEO" in header
    assert "Scanned" in header
    # A lead-only column proves the wrong catalogue was used.
    assert "Lead score" not in header


@asyncio_test
async def test_exporting_a_scan_from_another_organization_is_404(
    client: AsyncClient, signed_up_user
):
    _, headers = signed_up_user
    resp = await client.post(
        "/api/v1/exports",
        headers=headers,
        json={"resource": "website_scans", "format": "csv", "scan_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("fmt", ["csv", "excel", "pdf", "json"])
@asyncio_test
async def test_every_export_format_works_for_scans(
    client: AsyncClient, signed_up_user, db_session, fmt
):
    _, headers = signed_up_user
    await _make_scan(db_session, await _org_id(db_session))

    resp = await client.post(
        "/api/v1/exports", headers=headers, json={"resource": "website_scans", "format": fmt}
    )
    assert resp.status_code in (201, 202), f"{fmt}: {resp.text}"


def test_scan_row_never_invents_values():
    """An empty scan must produce empty cells, not placeholders."""
    bare = WebsiteScan(
        organization_id=uuid.uuid4(),
        url="https://x.test",
        domain="x.test",
        confidence_score=0,
        scan_duration_ms=1,
    )
    row = export_datasets.scan_row(bare)

    assert row["company_name"] is None
    assert row["emails"] == ""
    assert row["phones"] == ""
    assert row["gst_number"] is None
    assert row["seo_score"] is None
    # Booleans are rendered, because false is a finding — not a missing value.
    assert row["ssl_valid"] == "no"
    assert row["saved_as_lead"] == "no"


def test_scan_columns_are_selected_for_the_scan_resource():
    assert export_datasets.columns_for(ExportResource.WEBSITE_SCANS) is export_datasets.SCAN_COLUMNS
    assert export_datasets.columns_for(ExportResource.LEADS) is export_datasets.LEAD_COLUMNS


# --- Company matching by domain -------------------------------------------


@asyncio_test
async def test_a_lookalike_domain_is_not_treated_as_the_same_company(
    client: AsyncClient, signed_up_user, db_session
):
    """`Company.website ILIKE '%domain%'` merged unrelated companies.

    A scan of `apple.com` matched a stored `notapple.com` because the domain is
    a substring of it. The match is now decided by registrable domain.
    """
    from models.lead import Company

    impostor = Company(name="Not Apple Ltd", website="https://notapple.com")
    db_session.add(impostor)
    await db_session.commit()

    _, headers = signed_up_user
    scan = await _make_scan(
        db_session,
        await _org_id(db_session),
        url="https://apple.com",
        domain="apple.com",
        company_name="Apple",
        gst_number=None,
        gst_verified=False,
    )

    resp = await client.post(f"/api/v1/scans/{scan.id}/save-lead", headers=headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["company"] == "Apple", "a lookalike domain must not claim the lead"


@asyncio_test
async def test_a_subdomain_still_matches_the_same_company(
    client: AsyncClient, signed_up_user, db_session
):
    """The narrower match must not stop matching what it should.

    `normalize_domain` collapses subdomains to the registrable domain on purpose
    — `careers.acme.com` is the same business as `acme.com`.
    """
    from models.lead import Company

    acme = Company(name="Acme Industries", website="https://www.acme.com")
    db_session.add(acme)
    await db_session.commit()
    acme_id = acme.id

    _, headers = signed_up_user
    scan = await _make_scan(
        db_session,
        await _org_id(db_session),
        url="https://careers.acme.com",
        domain="careers.acme.com",
        company_name="Acme Industries Private Limited",
        gst_number=None,
        gst_verified=False,
    )

    resp = await client.post(f"/api/v1/scans/{scan.id}/save-lead", headers=headers)
    assert resp.status_code == 201, resp.text

    lead = (
        await db_session.execute(select(Lead).where(Lead.id == uuid.UUID(resp.json()["id"])))
    ).scalar_one()
    assert lead.company_id == acme_id, "the existing company should have been reused"
