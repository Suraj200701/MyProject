"""Maps `ApiProvider` database rows to concrete adapter instances.

Resolution order for credentials, most specific first:
  1. The provider row's own `api_key_encrypted` (decrypted via `utils.crypto`) —
     lets one workspace bring its own key.
  2. The platform-wide key from settings.
  3. Neither -> the adapter reports itself unconfigured and is skipped, so no
     credits are spent on a call that cannot succeed.

Provider rows are matched by name against the seeded catalogue. A row with no
adapter (e.g. "OpenAI GPT", which enriches rather than sources leads) is simply
not returned as a lead source — that is expected, not an error.
"""

from __future__ import annotations

import logging

from models.search import ApiProvider
from services.providers.base import LeadProvider
from services.providers.bing_search import BingSearchProvider
from services.providers.google_places import GooglePlacesProvider
from services.providers.mappls import MapplsProvider
from services.providers.website_search import WebsiteSearchProvider
from utils import crypto

logger = logging.getLogger("leadmaster.providers.registry")

# Provider-row name -> factory taking an optional per-row credential.
_ADAPTER_FACTORIES: dict[str, callable] = {
    "Google Places": lambda key: GooglePlacesProvider(api_key=key),
    "Mappls (MapmyIndia)": lambda key: MapplsProvider(client_id=None, client_secret=None),
    "Bing Search": lambda key: BingSearchProvider(api_key=key),
    "Company Website Search": lambda key: WebsiteSearchProvider(),
}

# Names that source leads. Anything else in the catalogue is enrichment-only.
LEAD_SOURCE_NAMES = frozenset(_ADAPTER_FACTORIES)


def _decrypt_row_key(row: ApiProvider) -> str | None:
    """Decrypts a per-provider key, tolerating an unconfigured/rotated keyring.

    A decryption failure must not break search — it degrades to the platform
    key (or to skipping the provider), and is logged loudly enough to notice.
    """
    if not row.api_key_encrypted:
        return None
    if not crypto.is_configured():
        logger.warning(
            "Provider %s has a stored credential but PROVIDER_CREDENTIAL_ENCRYPTION_KEY "
            "is not set — falling back to the platform key.",
            row.name,
        )
        return None
    try:
        return crypto.decrypt(row.api_key_encrypted)
    except crypto.DecryptionError:
        logger.error(
            "Could not decrypt the stored credential for provider %s — it may have been "
            "encrypted with a retired key. Falling back to the platform key.",
            row.name,
        )
        return None


def build_adapter(row: ApiProvider) -> LeadProvider | None:
    """Returns an adapter for this provider row, or None if it isn't a lead source."""
    factory = _ADAPTER_FACTORIES.get(row.name)
    if factory is None:
        return None
    return factory(_decrypt_row_key(row))


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
