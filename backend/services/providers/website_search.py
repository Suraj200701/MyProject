"""Company Website Search — crawls a company's own site for contact details.

This provider needs **no paid API**. Given a domain (or a lead that already has
a website), it fetches the homepage plus a small number of likely contact pages
and extracts real emails, phone numbers, GSTINs and social links from the
actual HTML.

Safety
------
Every fetch goes through `services.safe_http.safe_fetch`, which applies the
SSRF guard (scheme/port/hostname policy, DNS resolution, private/loopback/
link-local/cloud-metadata rejection, per-redirect revalidation) and enforces
timeout plus a streaming byte cap. This provider therefore cannot be used to
reach internal infrastructure, even though the domain comes from user input.

Crawl budget
------------
Deliberately shallow: the homepage plus at most `WEBSITE_CRAWL_MAX_PAGES - 1`
contact-ish pages discovered from homepage links. Contact details live on
`/contact`, `/about` or the footer in the overwhelming majority of business
sites, so a deep crawl buys little and costs latency, bandwidth and goodwill.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from config.settings import settings
from services.enrichment import extractors
from services.providers.base import (
    NormalizedLead,
    ProviderRunStatus,
    ProviderSearchResult,
    SearchQuery,
    failed,
)
from services.safe_http import FetchError, safe_fetch
from utils.exceptions import UnsafeUrlError

logger = logging.getLogger("leadmaster.providers.website")

# Link text / hrefs that tend to lead to contact information.
_CONTACT_HINTS = (
    "contact", "about", "reach-us", "reach_us", "get-in-touch",
    "enquiry", "enquiries", "inquiry", "support", "imprint", "impressum",
)


@dataclass
class WebsiteProfile:
    """Everything extracted from one company website."""

    url: str
    domain: str
    company_name: str | None = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    gstin: str | None = None
    gstin_rejected: list[str] = field(default_factory=list)
    social_links: list[dict] = field(default_factory=list)
    seo_signals: dict = field(default_factory=dict)
    seo_score: int = 0
    ssl_valid: bool = False
    mobile_friendly: bool = False
    load_time_ms: int = 0
    http_status: int | None = None
    pages_crawled: int = 0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.http_status is not None and self.http_status < 400


async def build_website_profile(raw_url: str, max_pages: int | None = None) -> WebsiteProfile:
    """Fetches and extracts a company website profile.

    Never raises for an unreachable or refused site — the failure is recorded on
    the returned profile so callers can persist a real "scan failed" outcome
    instead of a fabricated success.
    """
    budget = max_pages if max_pages is not None else settings.WEBSITE_CRAWL_MAX_PAGES

    try:
        first = await safe_fetch(raw_url)
    except UnsafeUrlError:
        # Propagate: an unsafe URL is a caller error (HTTP 400), not a site
        # that happens to be down.
        raise
    except FetchError as exc:
        parsed_domain = _safe_domain(raw_url)
        return WebsiteProfile(url=raw_url, domain=parsed_domain, error=str(exc))

    html = first.text
    domain = _safe_domain(first.final_url)

    profile = WebsiteProfile(
        url=first.final_url,
        domain=domain,
        http_status=first.status_code,
        ssl_valid=first.tls_used,
        load_time_ms=first.elapsed_ms,
        pages_crawled=1,
    )

    combined_html = [html]
    combined_text = [extractors.html_to_text(html)]

    for page_url in _find_contact_pages(html, first.final_url, budget - 1):
        try:
            extra = await safe_fetch(page_url)
        except (UnsafeUrlError, FetchError) as exc:
            logger.debug("Skipping contact page %s: %s", page_url, exc)
            continue
        if extra.status_code >= 400:
            continue
        combined_html.append(extra.text)
        combined_text.append(extractors.html_to_text(extra.text))
        profile.pages_crawled += 1

    all_html = "\n".join(combined_html)
    all_text = " ".join(combined_text)

    profile.company_name = extractors.extract_company_name(html, domain)
    profile.emails = extractors.extract_emails(all_text, all_html)
    profile.phones = extractors.extract_phones(all_text, all_html)

    gst = extractors.extract_gstin(all_text)
    profile.gstin = gst.primary
    profile.gstin_rejected = gst.invalid_checksum

    profile.social_links = extractors.extract_social_links(all_html)
    profile.seo_signals = extractors.extract_seo_signals(html)
    profile.seo_score = extractors.score_seo(profile.seo_signals)
    profile.mobile_friendly = bool(profile.seo_signals.get("has_viewport"))

    # Prefer contact emails on the company's own domain — a gmail address found
    # on a corporate site is more often an agency's than the company's.
    profile.emails = _prefer_own_domain(profile.emails, domain)
    return profile


class WebsiteSearchProvider:
    """Turns explicit domains in a query into enriched leads.

    Unlike the API providers, this one does not discover companies — it enriches
    ones already named. It activates when the query contains a domain or URL,
    which makes "just paste the company's website" a first-class search.
    """

    name = "Company Website Search"

    def __init__(self, max_pages: int | None = None):
        self._max_pages = max_pages

    @property
    def is_configured(self) -> bool:
        # No credentials needed — only the outbound-fetch feature flag.
        return settings.SCANNER_ENABLED

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        domains = _extract_domains(query.query)
        if not domains:
            return ProviderSearchResult(
                provider_name=self.name,
                status=ProviderRunStatus.SKIPPED,
                error="No website or domain found in the query",
            )

        leads: list[NormalizedLead] = []
        total_latency = 0
        errors: list[str] = []

        for domain in domains[: query.max_results]:
            try:
                profile = await build_website_profile(domain, self._max_pages)
            except UnsafeUrlError as exc:
                errors.append(f"{domain}: {exc.detail}")
                continue

            total_latency += profile.load_time_ms
            if not profile.succeeded:
                errors.append(f"{domain}: {profile.error or f'HTTP {profile.http_status}'}")
                continue

            leads.append(
                NormalizedLead(
                    company_name=profile.company_name or domain,
                    industry=query.industry,
                    website=profile.url,
                    gst_number=profile.gstin,
                    city=query.location,
                    country=query.country,
                    email=profile.emails[0] if profile.emails else None,
                    phone=profile.phones[0] if profile.phones else None,
                    tags=[t for t in [query.industry] if t],
                    raw={
                        "emails": profile.emails,
                        "phones": profile.phones,
                        "seo_score": profile.seo_score,
                        "pages_crawled": profile.pages_crawled,
                    },
                    source_provider=self.name,
                )
            )

        if not leads and errors:
            return failed(self.name, "; ".join(errors[:3]), latency_ms=total_latency)

        return ProviderSearchResult(
            provider_name=self.name,
            status=ProviderRunStatus.COMPLETED,
            leads=leads,
            error="; ".join(errors[:3]) if errors else None,
            latency_ms=total_latency,
        )


# --- helpers --------------------------------------------------------------

_DOMAIN_IN_TEXT_RE = re.compile(
    r"\b((?:https?://)?(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,24}(?:/[^\s]*)?)\b"
)
# Words that look like bare domains but are ordinary prose ("panel builders.in").
_NOT_A_DOMAIN_TLDS = frozenset({"in.", "co."})


def _extract_domains(text: str) -> list[str]:
    """Finds website/domain mentions in free text, preserving order."""
    found: dict[str, None] = {}
    for match in _DOMAIN_IN_TEXT_RE.finditer(text or ""):
        candidate = match.group(1).strip().rstrip(".,;:")
        host_part = candidate.split("://")[-1].split("/")[0].lower()
        if host_part.count(".") == 0:
            continue
        tld = host_part.rsplit(".", 1)[-1]
        if tld.isdigit() or len(tld) < 2:
            continue
        found.setdefault(candidate, None)
    return list(found)


def _safe_domain(url: str) -> str:
    try:
        host = (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()
    except ValueError:
        return ""
    return host.removeprefix("www.")


def _find_contact_pages(html: str, base_url: str, limit: int) -> list[str]:
    """Picks same-origin links most likely to carry contact details."""
    if limit <= 0 or not html:
        return []

    try:
        base_host = (urlparse(base_url).hostname or "").lower()
    except ValueError:
        return []

    soup = BeautifulSoup(html, "lxml")
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        try:
            parsed = urlparse(absolute)
        except ValueError:
            continue
        if parsed.scheme not in ("http", "https"):
            continue
        # Same-origin only: following off-site links would attribute another
        # company's contact details to this lead.
        if (parsed.hostname or "").lower() != base_host:
            continue

        normalized = absolute.split("#")[0]
        if normalized in seen or normalized.rstrip("/") == base_url.rstrip("/"):
            continue

        haystack = f"{parsed.path.lower()} {anchor.get_text(' ', strip=True).lower()}"
        for rank, hint in enumerate(_CONTACT_HINTS):
            if hint in haystack:
                seen.add(normalized)
                scored.append((rank, normalized))
                break

    scored.sort(key=lambda pair: pair[0])
    return [url for _, url in scored[:limit]]


def _prefer_own_domain(emails: list[str], domain: str) -> list[str]:
    """Sorts emails on the company's own domain first, preserving order within groups."""
    if not domain:
        return emails
    root = domain.removeprefix("www.")
    own = [e for e in emails if e.endswith(f"@{root}") or e.endswith(f".{root}")]
    other = [e for e in emails if e not in own]
    return own + other
