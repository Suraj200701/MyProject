"""Find the official website for a business we only have a name and address for.

Why this exists
---------------
Map-sourced leads (OpenStreetMap, Overpass, Mappls) arrive with a name and an
address and almost never a website. Measured on this deployment: 0 of 78 Bhopal
hospitals and 0 of 25 electrical businesses carried one, and Geoapify — being
OSM-derived — reports the same ~2%. Without a website there is nothing to crawl,
so contact enrichment cannot start.

Where candidates come from
--------------------------
The **official Google Places API**, and only when its key is configured.
`places:searchText` returns `websiteUri` as a first-class field: Google has
already resolved which site belongs to the business, so there is no searching,
no ranking and no guessing on our side.

Three things are deliberately *not* done here:

* **No domain guessing.** `acmeswitchgear.com` may belong to somebody else, and a
  plausible URL attached to the wrong company is worse than no URL.
* **No search-engine scraping, and no proxy rotation.** An earlier iteration used
  a SERP endpoint and was removed on both principle and evidence: for the query
  "Infosys" it returned LinkedIn, Wikipedia and `infosysbpm.com` but never
  `infosys.com`, and across six real businesses it accepted one website — the
  wrong one. Verification cannot rescue a candidate list that lacks the answer.
* **No Maps DOM reading.** Nothing here parses a rendered page.

Optionality is a hard requirement: with no Places key, discovery reports "not
configured" and the lead keeps an empty website. Enrichment then proceeds on
whatever public data already exists. It never fails the lead.

Verification
------------
Even an authoritative `websiteUri` is checked before use, because Places matched
on *its* idea of the business and we searched with *ours*. A cheap name/locality
comparison catches the case where the query resolved to a different company.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from config.settings import settings
from services.enrichment.dedup import normalize_company_name, normalize_domain
from services.providers.bing_search import _EXCLUDED_DOMAINS
from services.providers.google_places import SEARCH_TEXT_URL
from services.providers.http import (
    PermanentProviderError,
    TransientProviderError,
    request_json,
)
from services.providers.osm_common import TtlCache

logger = logging.getLogger("leadmaster.enrichment.discovery")

# Only what discovery needs. The field mask drives Google's billing tier, so
# asking for less keeps the request in the cheapest applicable SKU.
DISCOVERY_FIELD_MASK = (
    "places.displayName,places.websiteUri,places.formattedAddress,"
    "places.nationalPhoneNumber,places.id"
)

# A business name resolves to the same site for the life of a session, and each
# lookup costs a Places call, so results are cached per business key.
_DISCOVERY_CACHE = TtlCache()

# Accept at or above this. Places is authoritative about *its* match, so the bar
# is a sanity check rather than the adversarial scoring a SERP would need.
MIN_CONFIDENCE = 0.6

_WORD_RE = re.compile(r"[a-z0-9]+")

# Words too common to identify a business.
_GENERIC_TOKENS = frozenset({
    "the", "and", "pvt", "private", "ltd", "limited", "llp", "inc", "co",
    "company", "india", "indian", "services", "service", "solutions",
    "industries", "industrial", "enterprises", "enterprise", "group",
})


@dataclass
class DiscoveryResult:
    """Outcome of website discovery for one business."""

    website: str | None = None
    confidence: float = 0.0
    source: str | None = None
    signals: list[str] = field(default_factory=list)
    provider: str | None = None
    searched: bool = False
    error: str | None = None
    from_cache: bool = False
    # True when the provider answered but had no website for the business — a
    # normal outcome, distinct from "we never asked".
    provider_had_no_website: bool = False

    @property
    def found(self) -> bool:
        return self.website is not None


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {t for t in _WORD_RE.findall(value.lower()) if len(t) > 2 and t not in _GENERIC_TOKENS}


def is_usable_website(url: str | None) -> bool:
    """Whether a URL could be a company's own site.

    Excludes social profiles and directories: Places occasionally returns a
    Facebook page as a business's `websiteUri`, and contacts scraped there
    belong to the platform, not the company.
    """
    if not url or not url.startswith(("http://", "https://")):
        return False
    if not (urlparse(url).hostname or ""):
        return False
    return normalize_domain(url) not in _EXCLUDED_DOMAINS


class WebsiteDiscovery:
    """Resolves a business to its official website via Google Places."""

    provider_label = "Google Places"

    def __init__(self, api_key: str | None = None) -> None:
        # Read at call time so tests can monkeypatch settings, matching the
        # convention every provider client here follows.
        self._api_key = api_key or settings.GOOGLE_MAPS_API_KEY

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def discover(
        self,
        *,
        name: str,
        address: str | None = None,
        city: str | None = None,
        state: str | None = None,
        phone: str | None = None,
        category: str | None = None,
    ) -> DiscoveryResult:
        """Looks the business up and returns its verified website, if any."""
        if not name or not name.strip():
            return DiscoveryResult(error="No business name to search for.")

        if not self.is_configured:
            # The optional path. Not an error, and the caller continues.
            return DiscoveryResult(
                error="Google Places is not configured, so no website can be discovered."
            )

        key = f"{normalize_company_name(name)}|{(city or '').strip().lower()}"
        cached = _DISCOVERY_CACHE.get(key)
        if cached is not None:
            cached.from_cache = True
            return cached

        query = ", ".join(p for p in [name.strip(), address or city, state] if p)
        body = {"textQuery": query, "maxResultCount": 3}
        headers = {
            # Server-side only. The key never reaches a browser: this module runs
            # in the API process and the frontend calls our endpoint, not Google.
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": DISCOVERY_FIELD_MASK,
            "Content-Type": "application/json",
        }

        try:
            payload, _latency = await request_json(
                "POST", SEARCH_TEXT_URL, json_body=body, headers=headers
            )
        except (PermanentProviderError, TransientProviderError) as exc:
            logger.warning("Places discovery failed for %r: %s", name, exc)
            return DiscoveryResult(
                searched=True, provider=self.provider_label, error=str(exc)[:200]
            )

        places = payload.get("places") or []
        result = DiscoveryResult(searched=True, provider=self.provider_label)

        for place in places:
            website = place.get("websiteUri")
            if not is_usable_website(website):
                continue
            confidence, signals = self._score(
                place, name=name, city=city, phone=phone
            )
            if confidence >= MIN_CONFIDENCE:
                result.website = website
                result.confidence = round(confidence, 2)
                # The provider is the source of the *website*; the crawl records
                # its own per-page sources for the fields it extracts.
                result.source = f"Google Places ({place.get('id') or 'no id'})"
                result.signals = signals
                break
            result.signals = signals
            result.confidence = max(result.confidence, round(confidence, 2))

        if not result.found and places:
            result.provider_had_no_website = not any(
                is_usable_website(p.get("websiteUri")) for p in places
            )

        _DISCOVERY_CACHE.put(key, result)
        return result

    def _score(
        self, place: dict, *, name: str, city: str | None, phone: str | None
    ) -> tuple[float, list[str]]:
        """How confident we are that this Places result is the business we meant.

        Places already decided which website belongs to the place it matched.
        What this checks is whether it matched the *right place* — our query is
        a name plus a rough address, which can resolve to a similarly named
        business elsewhere.
        """
        signals: list[str] = []
        score = 0.0

        place_name = (place.get("displayName") or {}).get("text") or ""
        wanted, got = _tokens(name), _tokens(place_name)
        if wanted and got:
            overlap = len(wanted & got) / len(wanted)
            if overlap >= 0.8:
                score += 0.6
                signals.append(f"name matches Places result ({place_name})")
            elif overlap >= 0.5:
                score += 0.35
                signals.append(f"name partially matches ({place_name})")
            else:
                signals.append(f"name differs from Places result ({place_name})")

        formatted = (place.get("formattedAddress") or "").lower()
        if city and city.split(",")[0].strip().lower() in formatted:
            score += 0.25
            signals.append("locality matches")

        if phone:
            tail = "".join(ch for ch in str(phone) if ch.isdigit())[-10:]
            got_phone = re.sub(r"\D", "", place.get("nationalPhoneNumber") or "")
            if len(tail) == 10 and tail in got_phone:
                score += 0.3
                signals.append("phone matches")

        # The domain resembling the name is corroboration Places did not give us.
        website = place.get("websiteUri") or ""
        stem = normalize_domain(website).split(".")[0]
        if wanted and stem and any(t in stem for t in wanted if len(t) > 3):
            score += 0.15
            signals.append("domain resembles business name")

        return min(score, 1.0), signals
