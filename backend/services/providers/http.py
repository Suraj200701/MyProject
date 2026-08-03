"""Shared outbound HTTP for provider API calls.

Separate from `services/safe_http.py`: that module guards *user-supplied* URLs
against SSRF, whereas these are fixed, first-party provider endpoints where the
concerns are timeouts, retries and quota errors rather than SSRF.

Retries use `tenacity` with exponential backoff, and only for transient
conditions (timeouts, connection errors, 429, 5xx). A 4xx other than 429 means
the request itself is wrong — retrying would just burn quota.
"""

from __future__ import annotations

import logging
import time

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.settings import settings

logger = logging.getLogger("leadmaster.providers.http")


class TransientProviderError(Exception):
    """Retryable: timeout, connection failure, 429, or 5xx."""


class PermanentProviderError(Exception):
    """Not retryable: bad request, bad credentials, forbidden, not found."""


@retry(
    retry=retry_if_exception_type(TransientProviderError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.4, min=0.4, max=3),
    reraise=True,
)
async def request_json(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    form_body: dict | None = None,
    headers: dict | None = None,
    timeout: float | None = None,
) -> tuple[dict, int]:
    """Performs a provider API call. Returns `(parsed_json, latency_ms)`.

    `form_body` sends `application/x-www-form-urlencoded` — needed for OAuth2
    token exchanges (RFC 6749), and preferable to `params` for credentials
    because a request body does not land in proxy or access logs the way a
    query string does.

    Raises `TransientProviderError` (after retries are exhausted) or
    `PermanentProviderError`; adapters convert these into a FAILED
    `ProviderSearchResult` rather than letting them reach the request handler.
    """
    effective_timeout = timeout or settings.PROVIDER_TIMEOUT_SECONDS
    started = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            response = await client.request(
                method, url, params=params, json=json_body, data=form_body, headers=headers or {}
            )
    except httpx.TimeoutException as exc:
        raise TransientProviderError(f"Timed out after {effective_timeout}s") from exc
    except httpx.HTTPError as exc:
        raise TransientProviderError(f"Connection error: {type(exc).__name__}") from exc

    latency_ms = int((time.perf_counter() - started) * 1000)

    if response.status_code == 429:
        raise TransientProviderError("Rate limited by provider (429)")
    if response.status_code >= 500:
        raise TransientProviderError(f"Provider server error ({response.status_code})")
    if response.status_code in (401, 403):
        raise PermanentProviderError(
            f"Authentication rejected ({response.status_code}) — check the provider API key"
        )
    if response.status_code >= 400:
        # Include a short slice of the body: provider 4xx messages are usually
        # the fastest route to diagnosing a malformed query.
        raise PermanentProviderError(f"Provider rejected the request ({response.status_code}): {response.text[:200]}")

    # "No results" is a success, not a parse failure. Mappls answers 204 with an
    # empty body when a query matches nothing; without this the adapter would
    # report a working provider as FAILED and surface an error to the user.
    if response.status_code == 204 or not response.content:
        return {}, latency_ms

    try:
        return response.json(), latency_ms
    except ValueError as exc:
        raise PermanentProviderError(
            f"Provider returned a non-JSON response ({response.status_code}): {response.text[:200]}"
        ) from exc
