"""Bing Web Search adapter — discovers company websites from a search query.

⚠️ PROVISIONING CAVEAT — READ BEFORE BUDGETING FOR THIS
--------------------------------------------------------
Microsoft **retired the standalone Bing Search APIs on 11 August 2025**. New
Azure subscriptions can no longer create a "Bing Search v7" resource; the
successor is *Grounding with Bing Search*, consumed through Azure AI Agents
rather than as a direct search endpoint.

What that means here:
* If you hold a **pre-existing** Bing Search v7 resource, this adapter works
  as-is — set `BING_SEARCH_API_KEY` and it will query the v7 endpoint.
* If you do **not**, you cannot provision one, and this provider will simply
  report SKIPPED. The Company Website Search provider (`website_search.py`)
  covers much of the same ground without any paid dependency.
* `BING_SEARCH_ENDPOINT` is configurable precisely so a compatible or
  self-hosted gateway (or the Grounding-with-Bing shim, once you have one) can
  be pointed at without a code change.

This is implemented as asked, but flagged rather than left as a surprise at
procurement time.

What it produces
----------------
Bing returns web pages, not business records — so a result is a *company
website candidate*. The adapter derives a company name from the page title and
the registrable domain, and marks the lead for website enrichment (which then
extracts real emails/phones/GST from the page itself).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from config.settings import settings
from services.providers.base import (
    NormalizedLead,
    ProviderRunStatus,
    ProviderSearchResult,
    SearchQuery,
    failed,
    skipped,
)
from services.providers.http import (
    PermanentProviderError,
    TransientProviderError,
    request_json,
)

DEFAULT_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"
MAX_COUNT = 50

# Aggregators, directories and social sites: useful reading for a human, but
# they are not the lead's own website, so extracting contacts from them would
# attribute the aggregator's details to the company.
_EXCLUDED_DOMAINS = frozenset(
    {
        "facebook.com", "linkedin.com", "twitter.com", "x.com", "instagram.com",
        "youtube.com", "pinterest.com", "wikipedia.org", "quora.com", "reddit.com",
        "indiamart.com", "tradeindia.com", "justdial.com", "exportersindia.com",
        "yellowpages.com", "yelp.com", "glassdoor.com", "crunchbase.com",
        "zaubacorp.com", "tofler.in", "amazon.in", "amazon.com", "flipkart.com",
    }
)


class BingSearchProvider:
    """Finds candidate company websites via Bing Web Search."""

    name = "Bing Search"

    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        self._api_key = api_key or settings.BING_SEARCH_API_KEY
        self._endpoint = endpoint or settings.BING_SEARCH_ENDPOINT or DEFAULT_ENDPOINT

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        if not self.is_configured:
            return skipped(
                self.name,
                "BING_SEARCH_API_KEY is not configured (note: Bing Search v7 was "
                "retired for new Azure subscriptions in Aug 2025 — see module docs)",
            )

        # Over-fetch, because a large share of results are excluded aggregators.
        requested = max(1, min(query.max_results * 4, MAX_COUNT))
        params = {
            "q": query.full_text,
            "count": requested,
            "responseFilter": "Webpages",
            "textDecorations": "false",
        }
        market = _country_to_market(query.country)
        if market:
            params["mkt"] = market

        try:
            payload, latency_ms = await request_json(
                "GET",
                self._endpoint,
                params=params,
                headers={"Ocp-Apim-Subscription-Key": self._api_key},
            )
        except PermanentProviderError as exc:
            return failed(self.name, str(exc))
        except TransientProviderError as exc:
            return failed(self.name, f"Temporarily unavailable: {exc}")

        pages = ((payload.get("webPages") or {}).get("value")) or []
        leads: list[NormalizedLead] = []
        seen_domains: set[str] = set()

        for page in pages:
            lead = self._to_lead(page, query, seen_domains)
            if lead is not None:
                leads.append(lead)
            if len(leads) >= query.max_results:
                break

        return ProviderSearchResult(
            provider_name=self.name,
            status=ProviderRunStatus.COMPLETED,
            leads=leads,
            latency_ms=latency_ms,
        )

    def _to_lead(self, page: dict, query: SearchQuery, seen_domains: set[str]) -> NormalizedLead | None:
        url = page.get("url")
        if not url:
            return None
        try:
            host = (urlparse(url).hostname or "").lower().removeprefix("www.")
        except ValueError:
            return None
        if not host:
            return None

        registrable = _registrable_domain(host)
        if registrable in _EXCLUDED_DOMAINS or any(
            registrable.endswith(f".{d}") or registrable == d for d in _EXCLUDED_DOMAINS
        ):
            return None
        # One lead per company, not one per indexed page.
        if registrable in seen_domains:
            return None
        seen_domains.add(registrable)

        company_name = _company_name_from_page(page.get("name"), registrable)
        if not company_name:
            return None

        return NormalizedLead(
            company_name=company_name,
            industry=query.industry,
            website=f"https://{host}",
            city=query.location,
            country=query.country,
            tags=[t for t in [query.industry] if t],
            raw={"bing_url": url, "snippet": (page.get("snippet") or "")[:500]},
            source_provider=self.name,
        )


def _registrable_domain(host: str) -> str:
    """Approximate registrable domain (no Public Suffix List dependency).

    Handles the common multi-part suffixes this product actually encounters
    (`co.in`, `co.uk`, `com.au`, ...). A full PSL would be more precise; it is
    not worth a dependency here because the value is only used for
    de-duplication and aggregator exclusion, where an occasional over-broad
    match is harmless.
    """
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    two_part_suffixes = {"co", "com", "net", "org", "gov", "edu", "ac", "or", "ne"}
    if parts[-2] in two_part_suffixes and len(parts[-1]) <= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


_TITLE_NOISE_RE = re.compile(
    r"\b(home|homepage|welcome|official website|official site|contact us|about us|products?|services?)\b",
    re.IGNORECASE,
)


def _company_name_from_page(title: str | None, registrable_domain: str) -> str | None:
    """Derives a company name from a search-result title, falling back to the domain."""
    if title:
        cleaned = title
        for separator in ("|", "–", "—", " - ", "::", "»", ":"):
            if separator in cleaned:
                cleaned = cleaned.split(separator)[0]
                break
        cleaned = _TITLE_NOISE_RE.sub("", cleaned).strip(" -–—|:,")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) >= 3:
            return cleaned[:255]

    base = registrable_domain.split(".")[0]
    parts = [p for p in base.replace("_", "-").split("-") if p]
    derived = " ".join(p[:1].upper() + p[1:] for p in parts)
    return derived[:255] or None


_MARKETS = {
    "india": "en-IN",
    "united states": "en-US",
    "usa": "en-US",
    "united kingdom": "en-GB",
    "uk": "en-GB",
    "uae": "en-AE",
    "united arab emirates": "en-AE",
    "singapore": "en-SG",
    "australia": "en-AU",
    "canada": "en-CA",
}


def _country_to_market(country: str | None) -> str | None:
    if not country:
        return None
    return _MARKETS.get(country.strip().lower())
