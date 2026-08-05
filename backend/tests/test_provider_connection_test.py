"""Integration tests for `POST /providers/{id}/test` and the system checks.

Outbound HTTP is intercepted with an `httpx.MockTransport` rather than letting
the suite call Mappls/Google/Bing/OpenAI for real: a test that depends on a paid
third party is neither deterministic nor runnable offline. What is exercised for
real is everything we own — routing, the permission gate, credential resolution
through `registry.build_adapter`, latency measurement, error extraction, and the
provider-row status write-back.

The implementation itself makes genuine calls; that path is verified manually
against live Mappls credentials (see docs/API_TESTING.md).
"""

import json
import uuid

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update

from models.enums import ProviderStatus
from models.search import ApiProvider
from services import provider_test_service
from utils import crypto

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _provider(db_session, name: str) -> ApiProvider:
    db_session.expire_all()
    stmt = select(ApiProvider).where(ApiProvider.name == name)
    return (await db_session.execute(stmt)).scalar_one()


@pytest_asyncio.fixture(autouse=True)
async def _reset_providers(db_session):
    """Provider rows are seeded reference data that `_clean_tables` keeps, but
    credentials/status/latency are mutable state these tests write."""
    await db_session.execute(
        update(ApiProvider).values(
            api_key_encrypted=None,
            api_secret_encrypted=None,
            connected=False,
            status=ProviderStatus.HEALTHY,
            latency_ms=0,
        )
    )
    await db_session.commit()
    yield


@pytest.fixture
def encryption_configured(monkeypatch):
    monkeypatch.setattr(
        crypto.settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", crypto.generate_key(), raising=False
    )
    crypto._get_multi_fernet.cache_clear()
    yield
    crypto._get_multi_fernet.cache_clear()


class _HttpxShim:
    """Stands in for the `httpx` module inside the tester.

    Only `AsyncClient` is overridden (to inject a MockTransport); everything else
    — `HTTPStatusError`, `Request`, … — proxies to the real module so the tester's
    `except` clauses still match.

    Patching the module *reference* on `provider_test_service` rather than
    `httpx.AsyncClient` itself keeps the interception scoped to this module; the
    latter would swap it out globally, including for the ASGI test client.
    """

    def __init__(self, handler):
        self._handler = handler

    def __getattr__(self, name):
        return getattr(httpx, name)

    def AsyncClient(self, *args, **kwargs):  # noqa: N802 — mirrors httpx's name
        kwargs["transport"] = httpx.MockTransport(self._handler)
        return httpx.AsyncClient(*args, **kwargs)


def _mock_transport(monkeypatch, handler):
    """Routes every outbound httpx request in the tester through `handler`."""
    monkeypatch.setattr(provider_test_service, "httpx", _HttpxShim(handler))


# --- Mappls ---------------------------------------------------------------


async def test_mappls_success_reports_token_expiry(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    """The headline requirement: verify a token came back and report its expiry."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "outpost.mappls.com"
        # Credentials must travel in the body, never the query string.
        assert b"client_credentials" in request.content
        assert request.url.query == b""
        return httpx.Response(
            200,
            json={
                "access_token": "04118c85-a41a-47f7-bfac-dc5c31867da4",
                "token_type": "bearer",
                "expires_in": 82852,
                "scope": "READ",
                "project_code": "prj1785123669i1425431902",
            },
        )

    _mock_transport(monkeypatch, handler)
    # `provider_test_service.settings` is the one shared Settings instance every
    # module imports, so patching it here also changes what the Mappls adapter
    # reads. Credentials come from the platform values in this test; the
    # stored-credential path gets its own test below.
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_ID", "env-id", raising=False)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_SECRET", "env-secret", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "Mappls (MapmyIndia)")
    resp = await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["authenticated"] is True
    assert body["provider"] == "Mappls (MapmyIndia)"
    assert "23h" in body["message"]  # 82852s humanized
    assert body["details"]["expires_in_seconds"] == 82852
    assert body["details"]["scope"] == "READ"
    # The token itself must never cross the wire.
    assert "04118c85" not in resp.text
    assert body["details"]["token_length"] == 36


async def test_mappls_rejection_returns_200_with_full_diagnostics(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    """A failed test is a successful request — the provider is what failed.

    Returning 4xx/5xx here would be indistinguishable from the endpoint being
    broken, and the UI could not tell "your key is wrong" from "the API is down".
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text='{"error":"invalid_client"}')

    _mock_transport(monkeypatch, handler)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_ID", "bad", raising=False)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_SECRET", "bad", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "Mappls (MapmyIndia)")
    resp = await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["authenticated"] is False
    assert body["details"]["http_status"] == 401
    assert "invalid_client" in body["details"]["response_body"]
    assert "HTTPStatusError" in body["details"]["exception"]
    # No traceback over the wire — it exposes server paths.
    assert "Traceback" not in resp.text


async def test_mappls_200_without_token_is_not_a_success(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    """A 2xx that carries no token means the contract changed; don't claim success."""
    _mock_transport(monkeypatch, lambda request: httpx.Response(200, json={"token_type": "bearer"}))
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_ID", "x", raising=False)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_SECRET", "y", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "Mappls (MapmyIndia)")
    body = (await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)).json()

    assert body["success"] is False
    assert "no access_token" in body["message"]


async def test_unconfigured_provider_says_so_without_calling_out(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200, json={})

    _mock_transport(monkeypatch, handler)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_ID", "", raising=False)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_SECRET", "", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "Mappls (MapmyIndia)")
    body = (await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)).json()

    assert body["success"] is False
    assert "No credentials" in body["message"]
    assert "MAPPLS_CLIENT_ID" in body["details"]["hint"]
    assert called["n"] == 0, "must not fire a doomed request"


# --- Credential resolution matches production -----------------------------


async def test_test_uses_the_stored_credentials_not_the_environment(
    client: AsyncClient, signed_up_user, db_session, monkeypatch, encryption_configured
):
    """The test must authenticate with whatever a *search* would use.

    A tester that read settings directly could pass while search failed (or vice
    versa) whenever a workspace had its own credentials stored.
    """
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # Record the *token exchange* specifically. The tester also probes each
        # Mappls capability afterwards, and those are GETs with empty bodies —
        # recording every request would leave `seen["body"]` holding the last
        # empty one and fail for a reason that has nothing to do with which
        # credentials were used.
        if "oauth/token" in str(request.url):
            seen["body"] = request.content.decode()
            return httpx.Response(200, json={"access_token": "t" * 36, "expires_in": 3600})
        return httpx.Response(200, json={})

    _mock_transport(monkeypatch, handler)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_ID", "ENV-ID", raising=False)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_SECRET", "ENV-SECRET", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "Mappls (MapmyIndia)")
    await client.put(
        f"/api/v1/providers/{provider.id}/credentials",
        headers=headers,
        json={"api_key": "STORED-ID", "api_secret": "STORED-SECRET"},
    )

    resp = await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)
    assert resp.json()["success"] is True
    assert "STORED-ID" in seen["body"]
    assert "ENV-ID" not in seen["body"]


# --- Status write-back ----------------------------------------------------


async def test_successful_test_records_latency_and_health(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    _mock_transport(
        monkeypatch, lambda r: httpx.Response(200, json={"access_token": "t" * 36, "expires_in": 60})
    )
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_ID", "a", raising=False)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_SECRET", "b", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "Mappls (MapmyIndia)")
    await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)

    refreshed = await _provider(db_session, "Mappls (MapmyIndia)")
    assert refreshed.status is ProviderStatus.HEALTHY
    assert refreshed.latency_ms >= 0


async def test_failed_test_downgrades_a_healthy_provider(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    """A provider that just failed authentication must stop claiming to be healthy."""
    _mock_transport(monkeypatch, lambda r: httpx.Response(403, text="forbidden"))
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_ID", "a", raising=False)
    monkeypatch.setattr(provider_test_service.settings, "MAPPLS_CLIENT_SECRET", "b", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "Mappls (MapmyIndia)")
    assert provider.status is ProviderStatus.HEALTHY

    await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)

    assert (await _provider(db_session, "Mappls (MapmyIndia)")).status is ProviderStatus.DEGRADED


# --- Other providers ------------------------------------------------------


async def test_google_places_probe_uses_the_narrowest_field_mask(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    """Keeps the probe in the cheapest Places billing tier."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["mask"] = request.headers.get("X-Goog-FieldMask")
        captured["key"] = request.headers.get("X-Goog-Api-Key")
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"places": [{"id": "abc"}]})

    _mock_transport(monkeypatch, handler)
    monkeypatch.setattr(provider_test_service.settings, "GOOGLE_MAPS_API_KEY", "gkey", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "Google Places")
    body = (await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)).json()

    assert body["success"] is True
    assert captured["mask"] == "places.id"
    assert captured["key"] == "gkey"
    # httpx serializes without spaces, so compare parsed rather than by substring.
    assert json.loads(captured["body"]) == {"textQuery": "coffee", "maxResultCount": 1}
    assert body["details"]["places_returned"] == 1


async def test_bing_probe_requests_one_result(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        captured["key"] = request.headers.get("Ocp-Apim-Subscription-Key")
        return httpx.Response(200, json={"webPages": {"value": [{"url": "https://x.test"}]}})

    _mock_transport(monkeypatch, handler)
    monkeypatch.setattr(provider_test_service.settings, "BING_SEARCH_API_KEY", "bkey", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "Bing Search")
    body = (await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)).json()

    assert body["success"] is True
    assert captured["params"]["count"] == "1"
    assert captured["key"] == "bkey"


async def test_openai_probe_calls_the_models_endpoint(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]})

    _mock_transport(monkeypatch, handler)
    monkeypatch.setattr(provider_test_service.settings, "OPENAI_API_KEY", "sk-test", raising=False)

    _, headers = signed_up_user
    provider = await _provider(db_session, "OpenAI GPT")
    body = (await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)).json()

    assert body["success"] is True
    assert captured["url"] == "https://api.openai.com/v1/models"
    assert captured["auth"] == "Bearer sk-test"
    assert body["details"]["model_count"] == 2


async def test_uintegrated_catalogue_provider_reports_honestly(
    client: AsyncClient, signed_up_user, db_session
):
    """JustDial et al. have no adapter. Reporting success would be a lie."""
    _, headers = signed_up_user
    provider = await _provider(db_session, "JustDial")
    body = (await client.post(f"/api/v1/providers/{provider.id}/test", headers=headers)).json()

    assert body["success"] is False
    assert "no integration yet" in body["message"]


# --- Access control -------------------------------------------------------


async def test_test_endpoint_requires_authentication(client: AsyncClient, db_session):
    provider = await _provider(db_session, "Mappls (MapmyIndia)")
    resp = await client.post(f"/api/v1/providers/{provider.id}/test")
    assert resp.status_code in (401, 403)


async def test_unknown_provider_is_404(client: AsyncClient, signed_up_user):
    _, headers = signed_up_user
    resp = await client.post(f"/api/v1/providers/{uuid.uuid4()}/test", headers=headers)
    assert resp.status_code == 404


# --- System dependency checks --------------------------------------------


async def test_system_checks_cover_postgres_and_redis_for_real(
    client: AsyncClient, signed_up_user
):
    """No mocking here — these run against the suite's real Postgres and Redis."""
    _, headers = signed_up_user
    resp = await client.post("/api/v1/providers/system-checks", headers=headers)
    assert resp.status_code == 200, resp.text

    by_name = {entry["provider"]: entry for entry in resp.json()}
    assert by_name["PostgreSQL"]["success"] is True
    assert by_name["PostgreSQL"]["message"] == "SELECT 1 succeeded."
    assert by_name["Redis"]["success"] is True
    assert "PING" in by_name["Redis"]["message"]

    # SMTP and Stripe are unconfigured in the test environment; they must report
    # that rather than erroring or claiming success.
    assert by_name["SMTP"]["success"] is False
    assert "not configured" in by_name["SMTP"]["message"]
    assert by_name["Stripe"]["success"] is False
    assert "not configured" in by_name["Stripe"]["message"]


async def test_system_checks_require_the_manage_permission(client: AsyncClient):
    resp = await client.post("/api/v1/providers/system-checks")
    assert resp.status_code in (401, 403)
