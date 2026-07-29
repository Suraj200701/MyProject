"""Lead CRUD, notes, and org-scoping guarantees."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_and_list_lead(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user

    create_resp = await client.post(
        "/api/v1/leads",
        headers=headers,
        json={
            "company": "Acme Switchgear",
            "industry": "Panel Builders",
            "city": "Pune",
            "country": "India",
            "contact_name": "Jane Doe",
            "email": "jane@acmeswitchgear.com",
            "lead_score": 82,
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    lead = create_resp.json()
    assert lead["company"] == "Acme Switchgear"
    assert lead["lead_score"] == 82
    assert lead["status"] == "new"

    list_resp = await client.get("/api/v1/leads", headers=headers)
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["id"] == lead["id"]


async def test_lead_list_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/leads")
    assert resp.status_code == 401


async def test_update_lead_status_records_activity(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    create_resp = await client.post(
        "/api/v1/leads", headers=headers, json={"company": "Vertex Controls", "lead_score": 50}
    )
    lead_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/leads/{lead_id}", headers=headers, json={"status": "qualified"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "qualified"

    detail_resp = await client.get(f"/api/v1/leads/{lead_id}", headers=headers)
    activities = detail_resp.json()["activities"]
    assert any(a["event_type"] == "status_changed" for a in activities)


async def test_add_note_to_lead(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    create_resp = await client.post(
        "/api/v1/leads", headers=headers, json={"company": "Orbit Automation", "lead_score": 60}
    )
    lead_id = create_resp.json()["id"]

    note_resp = await client.post(
        f"/api/v1/leads/{lead_id}/notes", headers=headers, json={"text": "Called, left voicemail"}
    )
    assert note_resp.status_code == 201
    assert note_resp.json()["text"] == "Called, left voicemail"

    notes_resp = await client.get(f"/api/v1/leads/{lead_id}/notes", headers=headers)
    assert len(notes_resp.json()) == 1


async def test_lead_not_found_returns_404(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.get("/api/v1/leads/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404


async def test_leads_are_isolated_between_organizations(client: AsyncClient):
    """The core multi-tenancy guarantee: org A must never see org B's leads."""
    signup_a = await client.post(
        "/api/v1/auth/signup",
        json={"email": "orga@example.com", "password": "SecurePass123", "full_name": "A", "company_name": "Org A"},
    )
    headers_a = {"Authorization": f"Bearer {signup_a.json()['access_token']}"}

    signup_b = await client.post(
        "/api/v1/auth/signup",
        json={"email": "orgb@example.com", "password": "SecurePass123", "full_name": "B", "company_name": "Org B"},
    )
    headers_b = {"Authorization": f"Bearer {signup_b.json()['access_token']}"}

    create_resp = await client.post(
        "/api/v1/leads", headers=headers_a, json={"company": "Org A Only Lead", "lead_score": 70}
    )
    lead_id = create_resp.json()["id"]

    # Org B must not be able to see org A's lead in its list or by direct id.
    list_b = await client.get("/api/v1/leads", headers=headers_b)
    assert list_b.json()["meta"]["total_items"] == 0

    detail_b = await client.get(f"/api/v1/leads/{lead_id}", headers=headers_b)
    assert detail_b.status_code == 404
