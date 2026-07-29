"""Real Google OAuth 2.0 authorization-code flow (no SDK magic — plain
httpx calls against Google's documented endpoints, so behavior is easy to
audit). Requires GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET to be set."""

import httpx

from config.settings import settings
from utils.exceptions import BadRequestError

AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = "openid email profile"


def build_authorization_url(state: str) -> str:
    if not settings.GOOGLE_CLIENT_ID:
        raise BadRequestError("Google OAuth is not configured on this server (GOOGLE_CLIENT_ID missing)")

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
    return f"{AUTH_BASE_URL}?{query}"


async def exchange_code_for_tokens(code: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            },
        )
    if response.status_code != 200:
        raise BadRequestError(f"Google token exchange failed: {response.text}")
    return response.json()


async def fetch_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    if response.status_code != 200:
        raise BadRequestError(f"Failed to fetch Google profile: {response.text}")
    return response.json()
