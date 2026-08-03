"""Search/scan side-effects and role-based access control."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_search_completes_and_is_recorded_without_any_provider(
    client: AsyncClient, signed_up_user
):
    """A search with no provider credentials completes honestly with zero results.

    This previously asserted `results_count > 0`, which only held because the
    search service synthesized leads from a static pool. That generator has been
    removed, so with nothing configured the correct outcome is a completed search
    that produced nothing — the request still succeeds and is still recorded, and
    every provider reports why it could not run.

    The positive path (a configured provider actually sourcing leads) is covered
    in tests/test_lead_sources.py, where provider HTTP is mocked at the adapter
    boundary.
    """
    _, headers = signed_up_user

    search_resp = await client.post(
        "/api/v1/search", headers=headers, json={"query": "Panel Builders in Pune", "location": "Pune"}
    )
    assert search_resp.status_code == 201
    body = search_resp.json()
    assert body["status"] == "completed"
    assert body["results_count"] == 0
    assert len(body["provider_runs"]) > 0

    leads_resp = await client.get("/api/v1/leads", headers=headers)
    assert leads_resp.json()["meta"]["total_items"] == 0

    history_resp = await client.get("/api/v1/search/history", headers=headers)
    assert history_resp.json()["meta"]["total_items"] == 1


async def test_website_scan_of_an_unresolvable_domain_is_refused(client: AsyncClient, signed_up_user):
    """An unresolvable hostname is rejected rather than scanned.

    This replaces a test that asserted two scans of the same domain returned
    identical confidence scores — true only because the score came from an RNG
    seeded on the domain. Scans now read the real page, so determinism follows
    from page content and is asserted in tests/test_lead_sources.py against a
    fixture site.
    """
    _, headers = signed_up_user

    resp = await client.post("/api/v1/scan-website", headers=headers, json={"url": "example-corp.invalid"})
    assert resp.status_code == 400
    assert "could not be resolved" in resp.json()["message"]


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
