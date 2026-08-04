"""Production hardening of the ASGI app itself.

These are deployment-facing settings rather than request behaviour, so they build
their own app instances instead of using the shared `client` fixture — the app is
constructed once per process from the settings singleton, and the point here is
what happens under a *different* environment.
"""

import pytest
from fastapi.testclient import TestClient

from config.settings import Settings

DOC_ROUTES = ("/docs", "/redoc", "/openapi.json")


def _client_with(monkeypatch, **overrides) -> TestClient:
    """Builds a client for an app configured with patched settings.

    `main.create_app` reads the module-level singleton, so the override has to be
    installed on that object rather than passed in.

    The client is deliberately **not** used as a context manager, so the app's
    lifespan never runs. These tests assert which routes exist, which is decided
    at construction time — and running the lifespan would open a second Redis
    pool bound to this test's event loop rather than the session-scoped one the
    rest of the suite shares, failing with "attached to a different loop" as soon
    as another module has already initialised it.
    """
    import config.settings as settings_module
    import main

    patched = Settings(**overrides)
    monkeypatch.setattr(settings_module, "settings", patched)
    monkeypatch.setattr(main, "settings", patched)
    return TestClient(main.create_app())


@pytest.mark.parametrize("route", DOC_ROUTES)
def test_interactive_docs_are_not_served_in_production(monkeypatch, route):
    """A public host should not publish a map of every endpoint and schema.

    404, not 403: a refusal still confirms the route exists.
    """
    client = _client_with(monkeypatch, ENVIRONMENT="production")
    assert client.get(route).status_code == 404


@pytest.mark.parametrize("route", DOC_ROUTES)
def test_interactive_docs_are_served_outside_production(monkeypatch, route):
    client = _client_with(monkeypatch, ENVIRONMENT="development")
    assert client.get(route).status_code == 200


def test_docs_can_be_re_enabled_in_production(monkeypatch):
    """The environment default is a default, not a lock."""
    client = _client_with(monkeypatch, ENVIRONMENT="production", ENABLE_API_DOCS=True)
    assert client.get("/docs").status_code == 200


def test_health_is_reachable_with_docs_disabled(monkeypatch):
    """Disabling docs must not take the health check with it.

    The container healthcheck and every load balancer probe this route; if
    hardening broke it, the production stack would report itself unhealthy and
    restart forever.
    """
    client = _client_with(monkeypatch, ENVIRONMENT="production")
    assert client.get("/api/v1/health").status_code == 200


def test_scanner_does_not_reach_private_networks_by_default():
    """Default-deny SSRF guard.

    Left on, the scanner will fetch 169.254.169.254 and hand back the host's
    cloud credentials to whoever typed the URL.
    """
    assert Settings(ENVIRONMENT="production").SCANNER_ALLOW_PRIVATE_NETWORKS is False


def test_production_still_meters_credits():
    """The development metering bypass must not follow the app into production."""
    assert Settings(ENVIRONMENT="production").credit_metering_active is True
