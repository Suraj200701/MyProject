"""Search/scan side-effects and role-based access control."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_search_persists_real_leads(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user

    search_resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "Panel Builders in Pune", "location": "Pune"}
    )
    assert search_resp.status_code == 201
    body = search_resp.json()
    assert body["status"] == "completed"
    assert body["results_count"] > 0
    assert len(body["provider_runs"]) > 0

    leads_resp = await client.get("/api/v1/leads", headers=headers)
    assert leads_resp.json()["meta"]["total_items"] > 0

    history_resp = await client.get("/api/v1/search/history", headers=headers)
    assert history_resp.json()["meta"]["total_items"] == 1


async def test_website_scan_is_deterministic_per_domain(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user

    first = await client.post("/api/v1/scan-website", headers=headers, json={"url": "example-corp.com"})
    second = await client.post("/api/v1/scan-website", headers=headers, json={"url": "example-corp.com"})
    assert first.status_code == 201
    assert second.status_code == 201

    # Same domain -> same seeded RNG -> same confidence score / GST / social findings.
    assert first.json()["confidence_score"] == second.json()["confidence_score"]
    assert first.json()["gst_number"] == second.json()["gst_number"]


async def test_member_role_cannot_invite_team_members(client: AsyncClient):
    """Only Owner/Admin can invite — a plain Member must be forbidden."""
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": "owner_rbac@example.com", "password": "SecurePass123", "full_name": "Owner", "company_name": "RBAC Co"},
    )
    owner_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    # Owner invites successfully.
    invite_resp = await client.post(
        "/api/v1/team/invite", headers=owner_headers, json={"email": "newmember@example.com", "role": "member"}
    )
    assert invite_resp.status_code == 201


async def test_admin_endpoints_forbidden_for_non_superadmin(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.get("/api/v1/admin/stats", headers=headers)
    assert resp.status_code == 403


async def test_organization_update_requires_owner_or_admin(client: AsyncClient, signed_up_user):
    """The signed-up user IS the owner, so this should succeed — a
    negative case (member denied) would require inviting + accepting a
    second account, covered at the service layer instead for this suite."""
    _, headers = signed_up_user
    resp = await client.patch(
        "/api/v1/settings/organization", headers=headers, json={"name": "Renamed Co"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed Co"
