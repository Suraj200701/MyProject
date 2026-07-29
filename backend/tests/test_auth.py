"""Auth flow: signup, login, /me, wrong password, refresh, duplicate email."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_signup_creates_user_and_returns_tokens(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "founder@example.com",
            "password": "SecurePass123",
            "full_name": "Founder Name",
            "company_name": "Founder Co",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["email"] == "founder@example.com"
    assert data["user"]["role"]["name"] == "owner"
    assert data["user"]["is_email_verified"] is False


async def test_signup_duplicate_email_rejected(client: AsyncClient):
    payload = {
        "email": "dupe@example.com",
        "password": "SecurePass123",
        "full_name": "First",
        "company_name": "Co",
    }
    first = await client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409


async def test_signup_weak_password_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": "weak@example.com", "password": "short", "full_name": "X", "company_name": "Y"},
    )
    assert resp.status_code == 422


async def test_login_with_correct_credentials(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "login@example.com", "password": "SecurePass123", "full_name": "L", "company_name": "C"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "SecurePass123"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_login_with_wrong_password_rejected(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "wrongpw@example.com", "password": "SecurePass123", "full_name": "L", "company_name": "C"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "WrongPassword1"}
    )
    assert resp.status_code == 401


async def test_me_requires_bearer_token(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"].startswith("user_")


async def test_refresh_token_issues_new_access_token(client: AsyncClient, signed_up_user):
    data, _ = signed_up_user
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert resp.status_code == 200
    assert resp.json()["access_token"] != data["access_token"]


async def test_forgot_password_does_not_leak_account_existence(client: AsyncClient):
    resp = await client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@example.com"})
    assert resp.status_code == 200
    assert "if that email exists" in resp.json()["message"].lower()
