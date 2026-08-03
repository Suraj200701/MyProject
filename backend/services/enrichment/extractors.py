"""Contact-detail extraction from real web page content.

Every function here operates on actual fetched HTML/text — there is no
synthesized data. Extraction is deliberately conservative: a missing value is
returned as absent rather than guessed, because a fabricated email or GSTIN is
worse than no value at all (it pollutes the lead database and can get a sending
domain blacklisted).

What each extractor does
------------------------
* **Emails** — regex over page text plus `mailto:` hrefs, then a false-positive
  filter (asset filenames, tracking pixels, template placeholders, sentry/wix
  style build addresses). Role addresses (`sales@`, `info@`) are ranked above
  personal ones because they are stable and safe to contact.
* **Phones** — India-first (10 digits starting 6-9, with optional `+91`/`0`
  prefix and arbitrary separators) plus a generic international pattern,
  normalized to `+<country><number>`. Deliberately regex-based rather than
  pulling in `phonenumbers`: that library is excellent but ships a multi-MB
  metadata set, and this product's traffic is overwhelmingly Indian. The
  tradeoff is noted so it can be revisited if non-Indian coverage matters.
* **GSTIN** — shape match *and* the official mod-36 checksum. Shape alone
  accepts ~36x more false positives than it should, so the checksum is the
  thing that makes this trustworthy. Invalid-checksum candidates are reported
  separately rather than silently dropped, so a genuine format change is
  visible instead of looking like "no GST found".
* **Social links** — anchor hrefs matched against known platform domains,
  extracting the handle/page segment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# --- Email ----------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

# Substrings that mark an "email-shaped" string as not a real contact address.
_EMAIL_NOISE_SUBSTRINGS = (
    "example.com",
    "example.org",
    "domain.com",
    "yourdomain",
    "email@",
    "user@",
    "test@test",
    "sentry.io",
    "wixpress.com",
    "@sentry",
    "godaddy",
    "@2x",
    "no-reply@localhost",
)

# File extensions that appear in image/asset filenames like `logo@2x.png`.
_EMAIL_NOISE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js", ".woff", ".woff2", ".ico")

# Ranked highest-value first — role mailboxes are stable and safe to contact.
_ROLE_PREFIXES = ("sales", "info", "contact", "enquiry", "enquiries", "inquiry", "support", "hello", "admin", "office")


def extract_emails(text: str, html: str | None = None, limit: int = 10) -> list[str]:
    """Extracts plausible contact emails, best candidates first."""
    candidates: list[str] = [m.group(0) for m in _EMAIL_RE.finditer(text or "")]

    if html:
        # mailto: links are the highest-confidence source — someone explicitly
        # published that address as a contact point.
        soup = BeautifulSoup(html, "lxml")
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if href.lower().startswith("mailto:"):
                addr = href[7:].split("?")[0].strip()
                if addr:
                    candidates.insert(0, addr)

    seen: dict[str, None] = {}
    for raw in candidates:
        email = raw.strip().strip(".,;:()<>[]\"'").lower()
        if not _is_plausible_email(email):
            continue
        seen.setdefault(email, None)

    ordered = sorted(seen, key=_email_sort_key)
    return ordered[:limit]


def is_valid_email_syntax(email: str) -> bool:
    """Syntactic validity only — no placeholder/noise heuristics.

    This is the right check for an address a **user supplied** (CSV cell, manual
    entry form): they typed it deliberately, so the only question is whether it
    is a well-formed address. Applying the scraped-page noise filter here would
    silently discard real data the user asked us to store.
    """
    if not email or email.count("@") != 1:
        return False
    if len(email) > 254:
        return False
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        return False
    if email.endswith(_EMAIL_NOISE_SUFFIXES):
        return False  # a .png is never an address, however it was supplied
    # A TLD of digits means this is a version string, not a domain.
    if domain.rsplit(".", 1)[-1].isdigit():
        return False
    return True


def normalize_supplied_email(raw: str | None) -> str | None:
    """Cleans and validates a user-supplied address, or returns None."""
    if not raw:
        return None
    email = raw.strip().strip(".,;:()<>[]\"'").lower()
    return email if is_valid_email_syntax(email) else None


def _is_plausible_email(email: str) -> bool:
    """Validity plus the noise heuristics needed when *scraping* a page.

    Page HTML is full of email-shaped strings that are not contact addresses:
    template boilerplate (`you@yourdomain.com`), documentation placeholders
    (`user@example.com`), build/tracking addresses and asset filenames. Those
    heuristics are correct for scraped input and wrong for typed input, which is
    why `is_valid_email_syntax` exists separately.
    """
    if not is_valid_email_syntax(email):
        return False
    if any(noise in email for noise in _EMAIL_NOISE_SUBSTRINGS):
        return False
    return True


def _email_sort_key(email: str) -> tuple[int, int, str]:
    local = email.split("@", 1)[0]
    for rank, prefix in enumerate(_ROLE_PREFIXES):
        if local == prefix or local.startswith(f"{prefix}."):
            return (0, rank, email)
    return (1, 0, email)


# --- Phone ----------------------------------------------------------------

# Indian mobile: optional +91/0 prefix, then 10 digits starting 6-9.
#
# Separators are allowed between ANY digits rather than at fixed offsets,
# because Indian sites group numbers inconsistently — "98765 43210" (5-5),
# "987-654-3210" (3-3-4) and "9876543210" are all common. An earlier version
# hardcoded 3-3-4 and silently missed the 5-5 form, which is arguably the most
# common of the three.
#
# The lookarounds exclude *word* characters, not just digits, so a number
# embedded in an identifier ("INV9876543210") is not mistaken for a phone.
#
# The prefix spells out `0*91` rather than relying on backtracking: with a
# word-boundary lookbehind the engine can no longer re-anchor partway through a
# digit run, so "091-98765-43210" (trunk prefix *and* country code) has to be
# matched by the prefix in one pass or not at all.
_PHONE_IN_RE = re.compile(
    r"(?<![\w+])(?:\+?0*91[\-.\s]?|0)?([6-9](?:[\-.\s]?\d){9})(?![\w])"
)

# Indian landline: leading 0 (STD trunk prefix) then 9-10 more digits, i.e.
# 10-11 digits total, with separators permitted anywhere.
#
# Worth matching because many manufacturers list only a landline. Kept tight
# deliberately: the leading 0 is mandatory, the match cannot touch a word
# character on either side, and a "00" area code is rejected — without those
# guards this pattern happily matched invoice numbers like "INV0001234567",
# and a fabricated phone number is worse than a missing one.
_PHONE_IN_LANDLINE_RE = re.compile(
    r"(?<![\w+])(0(?:[\-.\s]?\d){9,10})(?![\w])"
)
# Generic international: +<1-3 digit cc> then 6-14 more digits with separators.
_PHONE_INTL_RE = re.compile(r"\+(\d{1,3})[\-.\s]?((?:\d[\-.\s]?){6,14}\d)")

# Strings that look like phone numbers but aren't (years, prices, IDs).
_MIN_DIGITS = 8
_MAX_DIGITS = 15


def extract_phones(text: str, html: str | None = None, default_country: str = "91", limit: int = 10) -> list[str]:
    """Extracts and normalizes phone numbers to `+<cc><digits>`."""
    found: dict[str, None] = {}

    if html:
        # tel: links, like mailto:, are explicit publisher intent.
        soup = BeautifulSoup(html, "lxml")
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if href.lower().startswith("tel:"):
                normalized = _normalize_phone(href[4:], default_country)
                if normalized:
                    found.setdefault(normalized, None)

    for match in _PHONE_INTL_RE.finditer(text or ""):
        normalized = _normalize_phone(f"+{match.group(1)}{match.group(2)}", default_country)
        if normalized:
            found.setdefault(normalized, None)

    for match in _PHONE_IN_RE.finditer(text or ""):
        normalized = _normalize_phone(match.group(1), default_country)
        if normalized:
            found.setdefault(normalized, None)

    # Landlines last: mobiles are the more useful outreach channel, so they
    # should occupy the earlier (preferred) slots when both are present.
    for match in _PHONE_IN_LANDLINE_RE.finditer(text or ""):
        digits = re.sub(r"\D", "", match.group(1))
        # 0 + 2-4 digit STD code + 6-8 subscriber digits. No Indian STD code
        # starts with 0, and that single check is what separates a landline from
        # a zero-padded serial number like "0001234567".
        if not (10 <= len(digits) <= 11) or digits[1] == "0":
            continue
        found.setdefault(f"+{default_country}{digits[1:]}", None)

    return list(found)[:limit]


def _normalize_phone(raw: str, default_country: str) -> str | None:
    if not raw:
        return None
    has_plus = raw.strip().startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None

    if has_plus:
        if not (_MIN_DIGITS <= len(digits) <= _MAX_DIGITS):
            return None
        return f"+{digits}"

    # Strip a domestic trunk prefix before applying the default country code.
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]

    if len(digits) == 10 and digits[0] in "6789":
        return f"+{default_country}{digits}"
    if _MIN_DIGITS <= len(digits) <= _MAX_DIGITS and len(digits) > 10:
        return f"+{digits}"
    return None


# --- GSTIN (India) --------------------------------------------------------

# 2-digit state code | 10-char PAN | 1 entity digit | 'Z' | 1 checksum char
_GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9])\b")
_GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Valid Indian GST state codes (01-38, plus 97 Other Territory / 99 Centre).
_VALID_STATE_CODES = {f"{i:02d}" for i in range(1, 39)} | {"97", "99"}


@dataclass
class GstinResult:
    """Outcome of GSTIN extraction.

    `valid` holds checksum-verified numbers. `invalid_checksum` holds
    correctly-shaped candidates that failed verification — surfaced rather than
    dropped so a real format change is visible in logs instead of silently
    looking like "no GST on this site".
    """

    valid: list[str] = field(default_factory=list)
    invalid_checksum: list[str] = field(default_factory=list)

    @property
    def primary(self) -> str | None:
        return self.valid[0] if self.valid else None


def gstin_checksum_char(first_14: str) -> str:
    """Computes the official GSTIN check character for the first 14 chars.

    Mod-36 weighted algorithm: walking right-to-left, each character's value is
    multiplied by an alternating factor of 1/2, the product is folded
    (quotient + remainder over 36), and the total's complement mod 36 maps back
    to a character.
    """
    if len(first_14) != 14:
        raise ValueError("GSTIN checksum requires exactly the first 14 characters")

    factor = 2
    total = 0
    for char in reversed(first_14.upper()):
        try:
            code = _GSTIN_ALPHABET.index(char)
        except ValueError as exc:
            raise ValueError(f"Invalid GSTIN character: {char!r}") from exc
        product = code * factor
        factor = 1 if factor == 2 else 2
        total += (product // 36) + (product % 36)
    return _GSTIN_ALPHABET[(36 - (total % 36)) % 36]


def is_valid_gstin(candidate: str) -> bool:
    """Full GSTIN validation: shape, state code, and checksum."""
    if not candidate:
        return False
    value = candidate.strip().upper()
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9]", value):
        return False
    if value[:2] not in _VALID_STATE_CODES:
        return False
    try:
        return gstin_checksum_char(value[:14]) == value[14]
    except ValueError:
        return False


def extract_gstin(text: str) -> GstinResult:
    """Finds GSTINs in page text, separating checksum-valid from invalid."""
    result = GstinResult()
    seen: set[str] = set()
    for match in _GSTIN_RE.finditer((text or "").upper()):
        candidate = match.group(1)
        if candidate in seen:
            continue
        seen.add(candidate)
        if is_valid_gstin(candidate):
            result.valid.append(candidate)
        else:
            result.invalid_checksum.append(candidate)
    return result


# --- Social links ---------------------------------------------------------

_SOCIAL_DOMAINS = {
    "LinkedIn": ("linkedin.com",),
    "Facebook": ("facebook.com", "fb.com"),
    "Instagram": ("instagram.com",),
    "X": ("twitter.com", "x.com"),
}

# Platform paths that are share/intent widgets rather than a company profile.
_SOCIAL_PATH_NOISE = ("sharer", "share", "intent", "login", "signup", "home", "plugins")


def extract_social_links(html: str) -> list[dict]:
    """Returns `[{platform, found, handle}]` for every known platform.

    Always includes all four platforms so the shape is stable for the frontend
    (which renders a fixed row per platform), with `found=False` when absent.
    """
    handles: dict[str, str | None] = {platform: None for platform in _SOCIAL_DOMAINS}

    if html:
        soup = BeautifulSoup(html, "lxml")
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if not href.lower().startswith(("http://", "https://")):
                continue
            try:
                parsed = urlparse(href)
            except ValueError:
                continue
            host = (parsed.hostname or "").lower().removeprefix("www.")
            path = parsed.path.strip("/")
            if not path or any(noise in path.lower() for noise in _SOCIAL_PATH_NOISE):
                continue

            for platform, domains in _SOCIAL_DOMAINS.items():
                if handles[platform] is not None:
                    continue
                if any(host == d or host.endswith(f".{d}") for d in domains):
                    handle = path.split("/")[0] if platform != "LinkedIn" else "/".join(path.split("/")[:2])
                    if handle:
                        handles[platform] = f"@{handle}" if not handle.startswith("@") else handle

    return [
        {"platform": platform, "found": handles[platform] is not None, "handle": handles[platform]}
        for platform in _SOCIAL_DOMAINS
    ]


# --- Page-level helpers ---------------------------------------------------


def html_to_text(html: str) -> str:
    """Strips scripts/styles and collapses whitespace for regex extraction."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def extract_company_name(html: str, fallback_domain: str = "") -> str | None:
    """Best-effort company name from OG tags, then <title>, then the domain."""
    if html:
        soup = BeautifulSoup(html, "lxml")
        og = soup.find("meta", attrs={"property": "og:site_name"}) or soup.find(
            "meta", attrs={"property": "og:title"}
        )
        if og and og.get("content"):
            name = _clean_title(og["content"])
            if name:
                return name
        if soup.title and soup.title.string:
            name = _clean_title(soup.title.string)
            if name:
                return name

    if fallback_domain:
        base = fallback_domain.split(".")[0]
        parts = [p for p in base.replace("_", "-").split("-") if p]
        return " ".join(p[:1].upper() + p[1:] for p in parts) or None
    return None


def _clean_title(raw: str) -> str | None:
    """Trims marketing suffixes: 'Acme Ltd | Panel Builders in Pune' -> 'Acme Ltd'."""
    if not raw:
        return None
    title = re.sub(r"\s+", " ", raw).strip()
    for separator in ("|", "–", "—", " - ", "::", "»"):
        if separator in title:
            title = title.split(separator)[0].strip()
            break
    return title[:255] or None


def extract_seo_signals(html: str) -> dict:
    """Real on-page SEO/mobile signals — no scoring API required.

    Each value is an observable property of the fetched document, so the
    derived score reflects the actual page rather than a random number.
    """
    if not html:
        return {
            "has_title": False,
            "has_meta_description": False,
            "has_h1": False,
            "has_viewport": False,
            "image_count": 0,
            "images_with_alt": 0,
            "internal_links": 0,
        }

    soup = BeautifulSoup(html, "lxml")
    images = soup.find_all("img")
    return {
        "has_title": bool(soup.title and (soup.title.string or "").strip()),
        "has_meta_description": bool(
            soup.find("meta", attrs={"name": "description"})
            or soup.find("meta", attrs={"property": "og:description"})
        ),
        "has_h1": bool(soup.find("h1")),
        # A viewport meta tag is the single strongest cheap indicator that a
        # page was built responsively — used in place of a paid PageSpeed call.
        "has_viewport": bool(soup.find("meta", attrs={"name": "viewport"})),
        "image_count": len(images),
        "images_with_alt": sum(1 for img in images if img.get("alt")),
        "internal_links": len(soup.find_all("a", href=True)),
    }


def score_seo(signals: dict) -> int:
    """Turns real page signals into a 0-100 SEO score."""
    score = 0
    if signals.get("has_title"):
        score += 25
    if signals.get("has_meta_description"):
        score += 20
    if signals.get("has_h1"):
        score += 15
    if signals.get("has_viewport"):
        score += 15
    image_count = signals.get("image_count", 0)
    if image_count:
        alt_ratio = signals.get("images_with_alt", 0) / image_count
        score += int(15 * alt_ratio)
    else:
        score += 8  # no images is neutral, not a failure
    if signals.get("internal_links", 0) >= 5:
        score += 10
    return max(0, min(100, score))
