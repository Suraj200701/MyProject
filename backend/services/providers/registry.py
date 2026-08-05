"""Maps `ApiProvider` database rows to concrete adapter instances.

Resolution order for credentials, most specific first:
  1. The provider row's own encrypted credentials (`api_key_encrypted`, and
     `api_secret_encrypted` for providers that authenticate with a pair) —
     lets one workspace bring its own keys, editable from the API Manager.
  2. The platform-wide values from settings / `.env`.
  3. Neither -> the adapter reports itself unconfigured and is skipped, so no
     credits are spent on a call that cannot succeed.

Provider rows are matched by name against the seeded catalogue. A row with no
adapter (e.g. "OpenAI GPT", which enriches rather than sources leads) is simply
not returned as a lead source — that is expected, not an error.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from models.search import ApiProvider
from services.providers.base import LeadProvider
from services.providers.bing_search import BingSearchProvider
from services.providers.geoapify import GeoapifyProvider
from services.providers.google_places import GooglePlacesProvider
from services.providers.mappls import MapplsProvider
from services.providers.openstreetmap import OpenStreetMapProvider
from services.providers.overpass import OverpassProvider
from services.providers.website_search import WebsiteSearchProvider
from utils import crypto

logger = logging.getLogger("leadmaster.providers.registry")


@dataclass(frozen=True)
class CredentialSpec:
    """What a provider needs to authenticate, and what to call it in the UI.

    `secret_label is None` means the provider takes a single value; Mappls is
    the one that needs a pair (client id + secret) for its OAuth exchange.
    """

    key_label: str
    key_env_var: str
    secret_label: str | None = None
    secret_env_var: str | None = None
    help_url: str | None = None


# Provider-row name -> what credentials it accepts. Also drives the API
# Manager's Credentials form, so the labels live here rather than in the client.
PROVIDER_CREDENTIAL_SPECS: dict[str, CredentialSpec] = {
    "Google Places": CredentialSpec(
        key_label="API key",
        key_env_var="GOOGLE_MAPS_API_KEY",
        help_url="https://developers.google.com/maps/documentation/places/web-service/get-api-key",
    ),
    "Mappls (MapmyIndia)": CredentialSpec(
        key_label="Client ID",
        key_env_var="MAPPLS_CLIENT_ID",
        secret_label="Client secret",
        secret_env_var="MAPPLS_CLIENT_SECRET",
        help_url="https://apis.mappls.com/console/",
    ),
    "Bing Search": CredentialSpec(
        key_label="API key",
        key_env_var="BING_SEARCH_API_KEY",
        help_url="https://portal.azure.com/",
    ),
    # Not a lead source: it holds a credential but has no adapter, so it never
    # appears in a search's provider runs. It is a fetch backend for the
    # website-crawling path — see services/providers/scraperapi.py.
    "ScraperAPI": CredentialSpec(
        key_label="API key",
        key_env_var="SCRAPERAPI_KEY",
        help_url="https://dashboard.scraperapi.com/",
    ),
    "Geoapify": CredentialSpec(
        key_label="API key",
        key_env_var="GEOAPIFY_API_KEY",
        help_url="https://myprojects.geoapify.com/",
    ),
}

# Provider-row name -> factory taking the decrypted (key, secret) pair.
_ADAPTER_FACTORIES: dict[str, callable] = {
    "Google Places": lambda key, secret: GooglePlacesProvider(api_key=key),
    "Mappls (MapmyIndia)": lambda key, secret: MapplsProvider(client_id=key, client_secret=secret),
    "Bing Search": lambda key, secret: BingSearchProvider(api_key=key),
    "Geoapify": lambda key, secret: GeoapifyProvider(api_key=key),
    # Public OSM services: no credential exists to pass, which is why they are
    # absent from PROVIDER_CREDENTIAL_SPECS above.
    "OpenStreetMap": lambda key, secret: OpenStreetMapProvider(),
    "Overpass API": lambda key, secret: OverpassProvider(),
    # Crawls sites found from the query itself — no third-party credential.
    "Company Website Search": lambda key, secret: WebsiteSearchProvider(),
}

# Names that source leads. Anything else in the catalogue is enrichment-only.
LEAD_SOURCE_NAMES = frozenset(_ADAPTER_FACTORIES)


def _decrypt(ciphertext: str | None, provider_name: str, field: str) -> str | None:
    """Decrypts one stored credential, tolerating an unconfigured/rotated keyring.

    A decryption failure must not break search — it degrades to the platform
    key (or to skipping the provider), and is logged loudly enough to notice.
    """
    if not ciphertext:
        return None
    if not crypto.is_configured():
        logger.warning(
            "Provider %s has a stored %s but PROVIDER_CREDENTIAL_ENCRYPTION_KEY "
            "is not set — falling back to the platform value.",
            provider_name,
            field,
        )
        return None
    try:
        return crypto.decrypt(ciphertext)
    except crypto.DecryptionError:
        logger.error(
            "Could not decrypt the stored %s for provider %s — it may have been "
            "encrypted with a retired key. Falling back to the platform value.",
            field,
            provider_name,
        )
        return None


def resolve_credentials(row: ApiProvider) -> tuple[str | None, str | None]:
    """The `(key, secret)` this provider row authenticates with.

    Exactly what `build_adapter` hands its factory, exposed separately so
    connectivity testing can authenticate with the same values a search would
    without reaching into an adapter's private attributes. `None` means "fall
    back to the platform value in settings", which each adapter does itself.
    """
    return (
        _decrypt(row.api_key_encrypted, row.name, "API key"),
        _decrypt(getattr(row, "api_secret_encrypted", None), row.name, "API secret"),
    )


def build_adapter(row: ApiProvider) -> LeadProvider | None:
    """Returns an adapter for this provider row, or None if it isn't a lead source."""
    factory = _ADAPTER_FACTORIES.get(row.name)
    if factory is None:
        return None
    key = _decrypt(row.api_key_encrypted, row.name, "API key")
    secret = _decrypt(getattr(row, "api_secret_encrypted", None), row.name, "API secret")
    return factory(key, secret)


def resolve_lead_providers(rows: list[ApiProvider]) -> list[tuple[ApiProvider, LeadProvider]]:
    """Pairs each lead-sourcing provider row with a usable adapter.

    Filters out rows that aren't lead sources and adapters that have no
    credentials, so callers only see providers that can actually run.
    """
    resolved: list[tuple[ApiProvider, LeadProvider]] = []
    for row in rows:
        adapter = build_adapter(row)
        if adapter is None:
            continue
        if not adapter.is_configured:
            logger.info("Skipping provider %s — not configured", row.name)
            continue
        resolved.append((row, adapter))
    return resolved
