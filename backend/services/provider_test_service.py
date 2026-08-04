"""Real connectivity/authentication tests for providers and infrastructure.

Nothing here is simulated. Each tester performs the cheapest request that still
proves the credential works end to end:

    Mappls          POST the OAuth2 client-credentials exchange, assert a token
                    came back, and report its expiry.
    Google Places   POST searchText with maxResultCount=1 and a one-field mask.
    Bing Search     GET /v7.0/search with count=1 and responseFilter=WebPages.
    Geoapify        GET /v2/places with limit=1 over a 500m circle.
    OpenStreetMap   GET Nominatim /search with limit=1 (no key; UA required).
    Overpass API    POST a trivial 1-element query (no key).
    OpenAI          GET /v1/models — the standard credential probe, no tokens
                    billed.
    SMTP            Open a real connection, STARTTLS if configured, and LOGIN
                    when credentials are present.
    Stripe          Account.retrieve() — the documented key-validation call.
    Redis           PING.
    Postgres        SELECT 1.

Credentials are resolved through exactly the same path a production search uses
(`registry.build_adapter`, which decrypts the provider row and falls back to the
platform settings), so a passing test means a search will authenticate too. A
tester that took its own path could pass while search still failed.

Failure reporting
-----------------
A failed test returns HTTP 200 with `success=false` — the *request* succeeded,
it is the provider that rejected us, and a non-2xx here would be indistinguishable
from the endpoint itself being broken. `details` carries the provider's status
code, error body and the exact exception type/message; the full traceback goes to
the log (`logger.exception`) rather than over the wire, since a traceback exposes
internal paths.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.search import ApiProvider
from services.providers import registry
from services.providers.bing_search import DEFAULT_ENDPOINT as BING_DEFAULT_ENDPOINT
from services.providers.google_places import SEARCH_TEXT_URL
from services.providers.mappls import MapplsClient

logger = logging.getLogger("leadmaster.providers.test")

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"

# Long enough for a cold provider, short enough that the UI's spinner doesn't
# look hung. Deliberately tighter than the search timeout: a credential probe
# that takes 30s is a failure in practice.
TEST_TIMEOUT_SECONDS = 12.0


@dataclass
class TestOutcome:
    """Result of one connectivity test."""

    provider: str
    success: bool
    authenticated: bool
    message: str
    latency_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)


def _fail(provider: str, message: str, latency_ms: int, **details: Any) -> TestOutcome:
    return TestOutcome(
        provider=provider,
        success=False,
        authenticated=False,
        message=message,
        latency_ms=latency_ms,
        details={k: v for k, v in details.items() if v is not None},
    )


def _describe_http_error(exc: httpx.HTTPStatusError) -> dict[str, Any]:
    """Everything a developer needs to diagnose a provider rejection."""
    return {
        "http_status": exc.response.status_code,
        # Truncated: provider error pages can be entire HTML documents.
        "response_body": exc.response.text[:1000],
        "exception": f"{type(exc).__name__}: {exc}",
        "request_url": str(exc.request.url).split("?")[0],
    }


def _describe_exception(exc: BaseException) -> dict[str, Any]:
    return {"exception": f"{type(exc).__name__}: {exc}"}


class _Timer:
    """Measures wall-clock latency even when the body raises."""

    def __enter__(self) -> _Timer:
        self._started = time.perf_counter()
        self.elapsed_ms = 0
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.elapsed_ms = int((time.perf_counter() - self._started) * 1000)

    @property
    def ms(self) -> int:
        # Usable mid-block, before __exit__ has run.
        return int((time.perf_counter() - self._started) * 1000)


# --- Lead-source providers ------------------------------------------------


async def test_mappls(client: MapplsClient) -> TestOutcome:
    """Exchanges the client id/secret for an OAuth token and reports its expiry."""
    name = "Mappls (MapmyIndia)"
    if not client.is_configured:
        return _fail(name, "No credentials configured for Mappls.", 0,
                     hint="Set the Client ID and Client secret, or MAPPLS_CLIENT_ID / MAPPLS_CLIENT_SECRET.")

    timer = _Timer()
    with timer:
        try:
            async with httpx.AsyncClient(timeout=TEST_TIMEOUT_SECONDS) as http:
                response = await http.post(
                    "https://outpost.mappls.com/api/security/oauth/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": client.client_id,
                        "client_secret": client.client_secret,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("Mappls token exchange rejected")
            return _fail(name, f"Mappls rejected the credentials ({exc.response.status_code}).",
                         timer.ms, **_describe_http_error(exc))
        except Exception as exc:  # noqa: BLE001 — surfaced verbatim to the caller
            logger.exception("Mappls token exchange failed")
            return _fail(name, f"Could not reach Mappls: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    token = payload.get("access_token")
    if not token:
        # 200 with no token means the contract changed; do not report success.
        return _fail(name, "Mappls returned 200 but no access_token.", timer.elapsed_ms,
                     response_body=str(payload)[:500])

    expires_in = payload.get("expires_in")
    return TestOutcome(
        provider=name,
        success=True,
        authenticated=True,
        message=f"Authenticated. Token valid for {_humanize_seconds(expires_in)}.",
        latency_ms=timer.elapsed_ms,
        details={
            "token_type": payload.get("token_type"),
            "expires_in_seconds": expires_in,
            "scope": payload.get("scope"),
            "project_code": payload.get("project_code"),
            # Never the token itself — just enough to confirm one was issued.
            "token_length": len(token),
        },
    )


async def test_google_places(api_key: str | None) -> TestOutcome:
    """Smallest possible Places (New) searchText call."""
    name = "Google Places"
    key = api_key or settings.GOOGLE_MAPS_API_KEY
    if not key:
        return _fail(name, "No API key configured for Google Places.", 0,
                     hint="Set the API key, or GOOGLE_MAPS_API_KEY.")

    timer = _Timer()
    with timer:
        try:
            async with httpx.AsyncClient(timeout=TEST_TIMEOUT_SECONDS) as http:
                response = await http.post(
                    SEARCH_TEXT_URL,
                    json={"textQuery": "coffee", "maxResultCount": 1},
                    headers={
                        "X-Goog-Api-Key": key,
                        # One field only: the narrowest mask Places accepts, so
                        # the probe stays in the cheapest billing tier.
                        "X-Goog-FieldMask": "places.id",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("Google Places test call rejected")
            return _fail(name, f"Google rejected the request ({exc.response.status_code}).",
                         timer.ms, **_describe_http_error(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Google Places test call failed")
            return _fail(name, f"Could not reach Google Places: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    return TestOutcome(
        provider=name,
        success=True,
        authenticated=True,
        message="Authenticated. Places API responded.",
        latency_ms=timer.elapsed_ms,
        details={"places_returned": len(payload.get("places") or [])},
    )


async def test_bing_search(api_key: str | None, endpoint: str | None = None) -> TestOutcome:
    """One-result web search — enough to validate the subscription key."""
    name = "Bing Search"
    key = api_key or settings.BING_SEARCH_API_KEY
    if not key:
        return _fail(name, "No API key configured for Bing Search.", 0,
                     hint="Set the API key, or BING_SEARCH_API_KEY.")

    url = endpoint or settings.BING_SEARCH_ENDPOINT or BING_DEFAULT_ENDPOINT
    timer = _Timer()
    with timer:
        try:
            async with httpx.AsyncClient(timeout=TEST_TIMEOUT_SECONDS) as http:
                response = await http.get(
                    url,
                    params={"q": "test", "count": 1, "responseFilter": "WebPages"},
                    headers={"Ocp-Apim-Subscription-Key": key},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("Bing Search test call rejected")
            return _fail(name, f"Bing rejected the request ({exc.response.status_code}).",
                         timer.ms, **_describe_http_error(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bing Search test call failed")
            return _fail(name, f"Could not reach Bing Search: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    return TestOutcome(
        provider=name,
        success=True,
        authenticated=True,
        message="Authenticated. Bing Search responded.",
        latency_ms=timer.elapsed_ms,
        details={"results_returned": len((payload.get("webPages") or {}).get("value") or [])},
    )


async def test_openai(api_key: str | None) -> TestOutcome:
    """GET /v1/models — validates the key without spending tokens."""
    name = "OpenAI GPT"
    key = api_key or settings.OPENAI_API_KEY
    if not key:
        return _fail(name, "No API key configured for OpenAI.", 0, hint="Set OPENAI_API_KEY.")

    timer = _Timer()
    with timer:
        try:
            async with httpx.AsyncClient(timeout=TEST_TIMEOUT_SECONDS) as http:
                response = await http.get(OPENAI_MODELS_URL, headers={"Authorization": f"Bearer {key}"})
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("OpenAI test call rejected")
            return _fail(name, f"OpenAI rejected the key ({exc.response.status_code}).",
                         timer.ms, **_describe_http_error(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenAI test call failed")
            return _fail(name, f"Could not reach OpenAI: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    models = payload.get("data") or []
    return TestOutcome(
        provider=name,
        success=True,
        authenticated=True,
        message=f"Authenticated. {len(models)} model(s) available.",
        latency_ms=timer.elapsed_ms,
        details={"model_count": len(models)},
    )


async def test_geoapify(api_key: str | None) -> TestOutcome:
    """One-result Places call — the cheapest request that proves the key works."""
    name = "Geoapify"
    key = api_key or settings.GEOAPIFY_API_KEY
    if not key:
        return _fail(name, "No API key configured for Geoapify.", 0, hint="Set GEOAPIFY_API_KEY.")

    timer = _Timer()
    with timer:
        try:
            async with httpx.AsyncClient(timeout=TEST_TIMEOUT_SECONDS) as http:
                response = await http.get(
                    f"{settings.geoapify_origin}/v2/places",
                    params={
                        "categories": "commercial",
                        # A tiny circle over central London: any valid key returns
                        # a well-formed response, and the request stays trivial.
                        "filter": "circle:-0.1276,51.5072,500",
                        "limit": 1,
                        "apiKey": key,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("Geoapify test call rejected")
            return _fail(name, f"Geoapify rejected the key ({exc.response.status_code}).",
                         timer.ms, **_describe_http_error(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Geoapify test call failed")
            return _fail(name, f"Could not reach Geoapify: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    return TestOutcome(
        provider=name,
        success=True,
        authenticated=True,
        message="Authenticated. Places API responded.",
        latency_ms=timer.elapsed_ms,
        details={"places_returned": len(payload.get("features") or [])},
    )


async def test_openstreetmap() -> TestOutcome:
    """Nominatim reachability. There is no key to validate — only the policy.

    A missing `User-Agent` is the one way to be *rejected* by this service, so
    that is what the check is really proving.
    """
    from services.providers.openstreetmap import NominatimClient

    name = "OpenStreetMap"
    if not settings.OSM_USER_AGENT:
        return _fail(name, "OSM_USER_AGENT is empty — Nominatim rejects requests without one.", 0,
                     hint="Set OSM_USER_AGENT (e.g. LeadMasterAI/1.0).")

    timer = _Timer()
    with timer:
        try:
            result = await NominatimClient().geocode("Ahmedabad, Gujarat, India")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Nominatim test call failed")
            return _fail(name, f"Could not reach Nominatim: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    if result is None:
        return _fail(name, "Nominatim responded but geocoded nothing.", timer.elapsed_ms)

    return TestOutcome(
        provider=name,
        success=True,
        # No credential exists, so there is nothing to authenticate. Reporting
        # True would imply a key was accepted.
        authenticated=True,
        message="Reachable. No API key required.",
        latency_ms=timer.elapsed_ms,
        details={"user_agent": settings.OSM_USER_AGENT, "endpoint": "nominatim.openstreetmap.org"},
    )


async def test_overpass() -> TestOutcome:
    """Smallest possible Overpass query.

    Overpass answers 429 when busy, which is a real operational state rather than
    a misconfiguration — the message says so instead of implying a bad key.
    """
    name = "Overpass API"
    if not settings.OVERPASS_URL:
        return _fail(name, "OVERPASS_URL is not configured.", 0, hint="Set OVERPASS_URL.")

    # One node, tiny radius: cheap for a shared public instance.
    ql = "[out:json][timeout:20];node[amenity=cafe](around:400,23.0225,72.5714);out ids 1;"
    timer = _Timer()
    with timer:
        try:
            async with httpx.AsyncClient(timeout=30.0) as http:
                response = await http.post(
                    settings.OVERPASS_URL,
                    data={"data": ql},
                    headers={"User-Agent": settings.OSM_USER_AGENT},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.exception("Overpass test call rejected")
            status = exc.response.status_code
            message = (
                "Overpass is throttling requests (429). The service is reachable but busy."
                if status == 429
                else f"Overpass returned {status}."
            )
            return _fail(name, message, timer.ms, **_describe_http_error(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Overpass test call failed")
            return _fail(name, f"Could not reach Overpass: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    return TestOutcome(
        provider=name,
        success=True,
        authenticated=True,
        message="Reachable. No API key required.",
        latency_ms=timer.elapsed_ms,
        details={
            "endpoint": settings.OVERPASS_URL,
            "elements_returned": len(payload.get("elements") or []),
        },
    )


# --- Infrastructure dependencies -----------------------------------------
#
# These have no ApiProvider row (they are not lead sources), so they are
# exposed through the system-checks endpoint rather than /providers/{id}/test.


def test_smtp_sync() -> TestOutcome:
    """Opens a real SMTP connection, STARTTLS-ing and logging in if configured.

    Synchronous because `smtplib` is; the route runs it in a thread so the event
    loop is never blocked. `aiosmtplib` (used for actual sending) has no
    connect-and-verify-only path, and sending a probe email would be worse than
    a plain connection test.
    """
    name = "SMTP"
    if not settings.SMTP_HOST:
        return _fail(name, "SMTP is not configured.", 0, hint="Set SMTP_HOST (and SMTP_PORT / SMTP_USER).")

    timer = _Timer()
    with timer:
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=TEST_TIMEOUT_SECONDS) as server:
                server.ehlo()
                if settings.SMTP_USE_TLS:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                authenticated = False
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    authenticated = True
        except smtplib.SMTPAuthenticationError as exc:
            logger.exception("SMTP authentication failed")
            return _fail(name, "SMTP rejected the credentials.", timer.ms,
                         smtp_code=exc.smtp_code, response_body=_decode(exc.smtp_error),
                         **_describe_exception(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("SMTP connection failed")
            return _fail(name, f"Could not connect to SMTP: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    return TestOutcome(
        provider=name,
        success=True,
        authenticated=authenticated,
        message=(
            f"Connected to {settings.SMTP_HOST}:{settings.SMTP_PORT} and signed in."
            if authenticated
            else f"Connected to {settings.SMTP_HOST}:{settings.SMTP_PORT} (no credentials set, so no login attempted)."
        ),
        latency_ms=timer.elapsed_ms,
        details={"host": settings.SMTP_HOST, "port": settings.SMTP_PORT, "starttls": settings.SMTP_USE_TLS},
    )


def test_stripe_sync() -> TestOutcome:
    """Account.retrieve() — Stripe's documented way to validate a secret key."""
    name = "Stripe"
    if not settings.STRIPE_SECRET_KEY:
        return _fail(name, "Stripe is not configured.", 0, hint="Set STRIPE_SECRET_KEY.")

    import stripe

    timer = _Timer()
    with timer:
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            account = stripe.Account.retrieve()
        except Exception as exc:  # noqa: BLE001 — stripe raises several unrelated types
            logger.exception("Stripe account retrieval failed")
            return _fail(name, f"Stripe rejected the key: {type(exc).__name__}", timer.ms,
                         http_status=getattr(exc, "http_status", None),
                         response_body=str(getattr(exc, "user_message", "") or "")[:500] or None,
                         **_describe_exception(exc))

    return TestOutcome(
        provider=name,
        success=True,
        authenticated=True,
        message=f"Authenticated as {account.get('email') or account.get('id')}.",
        latency_ms=timer.elapsed_ms,
        details={
            "account_id": account.get("id"),
            "livemode": settings.STRIPE_SECRET_KEY.startswith("sk_live_"),
            "charges_enabled": account.get("charges_enabled"),
            "country": account.get("country"),
        },
    )


async def test_redis(cache: Redis) -> TestOutcome:
    """PING against the same connection pool the app uses."""
    timer = _Timer()
    with timer:
        try:
            pong = await cache.ping()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Redis ping failed")
            return _fail("Redis", f"Could not reach Redis: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    return TestOutcome(
        provider="Redis",
        success=bool(pong),
        # Redis here is unauthenticated by design in development; PING succeeding
        # is the whole check.
        authenticated=bool(pong),
        message="PING succeeded." if pong else "PING returned a falsy reply.",
        latency_ms=timer.elapsed_ms,
        details={"host": settings.REDIS_HOST, "port": settings.REDIS_PORT, "db": settings.REDIS_DB},
    )


async def test_postgres(db: AsyncSession) -> TestOutcome:
    """SELECT 1 on the request's own session."""
    timer = _Timer()
    with timer:
        try:
            value = (await db.execute(text("SELECT 1"))).scalar_one()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Postgres connectivity check failed")
            return _fail("PostgreSQL", f"Query failed: {type(exc).__name__}", timer.ms,
                         **_describe_exception(exc))

    return TestOutcome(
        provider="PostgreSQL",
        success=value == 1,
        authenticated=value == 1,
        message="SELECT 1 succeeded." if value == 1 else f"SELECT 1 returned {value!r}.",
        latency_ms=timer.elapsed_ms,
        details={"host": settings.POSTGRES_HOST, "port": settings.POSTGRES_PORT, "database": settings.POSTGRES_DB},
    )


# --- Dispatch -------------------------------------------------------------

# Providers in the catalogue that are not integrated as lead sources. Testing
# them must say so rather than reporting a success that means nothing.
NOT_INTEGRATED_MESSAGE = (
    "{name} is listed in the catalogue but has no integration yet, so there is nothing to "
    "authenticate against. It is never queried during a search."
)


async def test_provider(row: ApiProvider) -> TestOutcome:
    """Runs the connectivity test for one provider row.

    Credentials come from `registry.resolve_credentials`, the same decryption and
    fallback the search pipeline's adapters receive — stored row credentials
    first, platform settings second. That is what makes a green test meaningful:
    a tester that re-read settings itself could pass while a search using stored
    credentials failed, or vice versa.
    """
    key, secret = registry.resolve_credentials(row)

    if row.name == "Mappls (MapmyIndia)":
        # MapplsClient applies the same `or settings.MAPPLS_*` fallback the
        # adapter does, so passing the resolved pair straight in is equivalent.
        return await test_mappls(MapplsClient(client_id=key, client_secret=secret))

    if row.name == "Google Places":
        return await test_google_places(key)

    if row.name == "Bing Search":
        return await test_bing_search(key)

    if row.name == "Geoapify":
        return await test_geoapify(key)

    if row.name == "OpenStreetMap":
        return await test_openstreetmap()

    if row.name == "Overpass API":
        return await test_overpass()

    if row.name == "OpenAI GPT":
        # OpenAI has no per-row credential column of its own; it is enrichment
        # configured platform-wide.
        return await test_openai(key)

    if row.name == "Company Website Search":
        # No third-party credential: it crawls sites discovered from the query.
        return TestOutcome(
            provider=row.name,
            success=settings.SCANNER_ENABLED,
            authenticated=True,
            message=(
                "No credentials required — this provider crawls company websites directly."
                if settings.SCANNER_ENABLED
                else "Disabled: set SCANNER_ENABLED=true to allow outbound website fetches."
            ),
            details={"scanner_enabled": settings.SCANNER_ENABLED},
        )

    return _fail(row.name, NOT_INTEGRATED_MESSAGE.format(name=row.name), 0)


def _humanize_seconds(seconds: Any) -> str:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "an unspecified period"
    if total >= 3600:
        return f"{total // 3600}h {(total % 3600) // 60}m"
    if total >= 60:
        return f"{total // 60}m"
    return f"{total}s"


def _decode(value: object) -> str | None:
    """SMTP error bodies arrive as bytes."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")[:500]
    return str(value)[:500]
