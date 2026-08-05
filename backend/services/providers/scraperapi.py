"""ScraperAPI — an optional fetch backend for the website-crawling path.

What this is for
----------------
`WebsiteSearchProvider` and the website scanner fetch company websites directly.
Plenty of real business sites sit behind WAFs that reject datacenter IPs outright,
so those fetches fail for reasons that have nothing to do with the site being
wrong. ScraperAPI is a paid proxy the operator subscribes to; routing a fetch
through it makes those requests succeed.

What this is deliberately NOT for
---------------------------------
It is not wired to Google Maps, or to any provider whose terms prohibit automated
access. Using a rotating-proxy service to get around another site's anti-bot
measures is exactly the bypass the Map Mode brief rules out — the fact that a
tool *can* do it is not permission. Map Mode sources its data from OpenStreetMap
and Overpass, which publish their data under an open licence and permit
programmatic access.

It is also not a `LeadProvider`: it sources no leads of its own, so it has no
adapter entry and never appears in a search's provider runs. It holds a
credential, which is why it has a `CredentialSpec`.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("leadmaster.providers.scraperapi")

PROVIDER_NAME = "ScraperAPI"

ACCOUNT_URL = "https://api.scraperapi.com/account"
FETCH_URL = "https://api.scraperapi.com/"

# Proxied fetches are slower than direct ones by design: the service retries
# upstream on our behalf before answering.
FETCH_TIMEOUT_SECONDS = 70.0
ACCOUNT_TIMEOUT_SECONDS = 20.0


class ScraperApiError(RuntimeError):
    """Raised when ScraperAPI itself refuses or fails a request."""


class ScraperApiClient:
    """Thin wrapper over the two endpoints this integration uses."""

    name = PROVIDER_NAME

    def __init__(self, api_key: str | None) -> None:
        self._api_key = (api_key or "").strip()

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def account(self) -> dict:
        """Returns the subscription's usage counters.

        This is the Test Connection probe: it is authenticated, cheap, and — per
        ScraperAPI's docs — does not consume a request from the plan, so testing
        a key does not cost the operator anything.
        """
        if not self.is_configured:
            raise ScraperApiError("No ScraperAPI key configured")

        async with httpx.AsyncClient(timeout=ACCOUNT_TIMEOUT_SECONDS) as client:
            response = await client.get(ACCOUNT_URL, params={"api_key": self._api_key})

        if response.status_code == 401:
            raise ScraperApiError("ScraperAPI rejected the key (401)")
        response.raise_for_status()
        return response.json()

    async def fetch(self, url: str, *, render: bool = False) -> str:
        """Fetches `url` through the proxy and returns the response body.

        `render` asks ScraperAPI to execute JavaScript first. It costs
        substantially more credits per request, so it stays opt-in.
        """
        if not self.is_configured:
            raise ScraperApiError("No ScraperAPI key configured")

        params: dict[str, str] = {"api_key": self._api_key, "url": url}
        if render:
            params["render"] = "true"

        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS) as client:
            response = await client.get(FETCH_URL, params=params)

        if response.status_code == 401:
            raise ScraperApiError("ScraperAPI rejected the key (401)")
        if response.status_code == 403:
            # ScraperAPI returns 403 when the *target* refused, not us.
            raise ScraperApiError(f"Target site refused the request ({url})")
        if response.status_code == 429:
            raise ScraperApiError("ScraperAPI concurrency limit reached")
        response.raise_for_status()
        return response.text
