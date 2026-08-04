"""Shared OpenStreetMap plumbing: politeness, caching, and tag extraction.

Both OSM providers (Nominatim geocoding and Overpass POI search) read the same
tag vocabulary and must observe the same courtesies, so that lives here once.

Why the politeness machinery is not optional
--------------------------------------------
These are free, donated, community-run services with published usage policies,
and they enforce them. Measured against the live APIs while building this:

* Nominatim **rejects requests without an identifying User-Agent** and caps
  callers at 1 request/second.
* Overpass returned **HTTP 429 on 8 of 12** probe requests spaced 1.2s apart,
  and **504** on a heavier one. Its error bodies are **HTML, not JSON**.

So: a process-wide rate limiter for Nominatim, a TTL cache in front of both, and
retry/backoff supplied by `providers.http.request_json` (which already treats 429
and 5xx as transient). Overpass callers additionally union everything into a
single query per search rather than issuing one request per tag — that was the
difference between working and being throttled.

Tag extraction
--------------
`extract_osm_fields` reads the documented OSM tag vocabulary. Values are only
ever read, never invented: a tag that is absent yields `None`, because a
fabricated phone number is worse than a missing one.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("leadmaster.providers.osm")

# Nominatim's policy ceiling. Enforced here rather than trusted to call sites,
# because a single accidental loop is enough to get an IP blocked.
NOMINATIM_MIN_INTERVAL_SECONDS = 1.1

# Responses are cached briefly: a user refining "restaurants in Ahmedabad" would
# otherwise re-ask an identical question of a donated service.
CACHE_TTL_SECONDS = 900
CACHE_MAX_ENTRIES = 256


class RateLimiter:
    """Serializes calls and enforces a minimum gap between them.

    Process-wide, not per-instance: the limit belongs to the remote service, so
    every adapter in this process must queue behind the same gate.
    """

    def __init__(self, min_interval: float):
        # Public and read at call time: a test suite that makes no real requests
        # has nothing to be polite about, and paying 1.1s per test would make the
        # delay the dominant cost of running them.
        self.min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()


class TtlCache:
    """Small FIFO cache with a time-to-live.

    Deliberately in-process rather than Redis: it exists to be polite to a public
    API, not to be a shared source of truth, and adding a Redis dependency to the
    provider layer would be a bigger change than the problem warrants.
    """

    def __init__(self, ttl: float = CACHE_TTL_SECONDS, max_entries: int = CACHE_MAX_ENTRIES):
        self._ttl = ttl
        self._max_entries = max_entries
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > self._ttl:
            self._entries.pop(key, None)
            return None
        return value

    def put(self, key: str, value: Any) -> None:
        if len(self._entries) >= self._max_entries:
            # Evict the oldest insertion; dicts preserve insertion order.
            self._entries.pop(next(iter(self._entries)), None)
        self._entries[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._entries.clear()


nominatim_limiter = RateLimiter(NOMINATIM_MIN_INTERVAL_SECONDS)
nominatim_cache = TtlCache()
overpass_cache = TtlCache()


# --- Tag vocabulary -------------------------------------------------------

# Keys that identify what a place *is*, most specific first. The first one
# present becomes the category.
_CATEGORY_KEYS = (
    "amenity",
    "shop",
    "office",
    "craft",
    "healthcare",
    "man_made",
    "industrial",
    "landuse",
    "tourism",
    "leisure",
    "building",
)

# Keys that refine the category (a restaurant's cuisine, a clinic's speciality).
_SUBCATEGORY_KEYS = (
    "cuisine",
    "healthcare:speciality",
    "shop",
    "vending",
    "product",
    "industry",
    "generator:source",
)

# Contact tags, in preference order. OSM allows both bare and `contact:`-prefixed
# forms for all of these; neither is more canonical than the other in practice.
_PHONE_KEYS = ("phone", "contact:phone", "telephone")
_MOBILE_KEYS = ("contact:mobile", "mobile", "phone:mobile")
_WEBSITE_KEYS = ("website", "contact:website", "url", "contact:url")
_EMAIL_KEYS = ("email", "contact:email")
_SOCIAL_KEYS = {
    "facebook": ("contact:facebook", "facebook"),
    "instagram": ("contact:instagram", "instagram"),
    "linkedin": ("contact:linkedin", "linkedin"),
    "twitter": ("contact:twitter", "twitter"),
    "youtube": ("contact:youtube", "youtube"),
    "whatsapp": ("contact:whatsapp", "whatsapp"),
}


def _first(tags: dict, keys: tuple[str, ...]) -> str | None:
    """First non-empty value among `keys`. None when none are present."""
    for key in keys:
        value = tags.get(key)
        if value not in (None, ""):
            # OSM values arrive as strings, but all-digit tags can be parsed as
            # numbers by intermediate layers, so coerce.
            return str(value).strip() or None
    return None


def osm_category(tags: dict) -> tuple[str | None, str | None]:
    """`(category, subcategory)` as human-readable labels.

    `amenity=restaurant` -> ("Restaurant", None); with `cuisine=indian` the
    subcategory becomes "Indian".
    """
    category = None
    for key in _CATEGORY_KEYS:
        value = tags.get(key)
        if value and value != "yes":
            category = str(value).replace("_", " ").title()
            break

    subcategory = None
    for key in _SUBCATEGORY_KEYS:
        value = tags.get(key)
        # Skip the key that already produced the category.
        if value and value != "yes" and str(value).replace("_", " ").title() != category:
            subcategory = str(value).replace("_", " ").replace(";", ", ").title()
            break

    return category, subcategory


def compose_address(tags: dict) -> str | None:
    """A street address assembled from `addr:*` tags.

    Built in the conventional reading order rather than alphabetically, and only
    from parts that exist — no placeholder commas for missing components.
    """
    parts = [
        " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p),
        tags.get("addr:suburb") or tags.get("addr:neighbourhood"),
        tags.get("addr:district"),
        tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"),
        tags.get("addr:state"),
        tags.get("addr:postcode"),
    ]
    joined = ", ".join(str(p).strip() for p in parts if p and str(p).strip())
    return joined or None


def payment_methods(tags: dict) -> list[str]:
    """Accepted payment methods, from `payment:*=yes` tags."""
    return sorted(
        key.split(":", 1)[1].replace("_", " ")
        for key, value in tags.items()
        if key.startswith("payment:") and str(value).lower() in ("yes", "only", "true")
    )


def social_links(tags: dict) -> dict[str, str]:
    """Social profiles present on the element, keyed by platform."""
    found: dict[str, str] = {}
    for platform, keys in _SOCIAL_KEYS.items():
        value = _first(tags, keys)
        if value:
            found[platform] = value
    return found


def extract_osm_fields(tags: dict) -> dict[str, Any]:
    """Every public field this element carries, normalized.

    Absent tags map to `None` (or an empty collection). Nothing is defaulted,
    guessed or back-filled — the spec for this integration is explicit that a
    missing value stays missing.
    """
    category, subcategory = osm_category(tags)
    return {
        "name": _first(tags, ("name", "name:en", "official_name", "brand")),
        "category": category,
        "subcategory": subcategory,
        "address": compose_address(tags),
        "street": _first(tags, ("addr:street",)),
        "housenumber": _first(tags, ("addr:housenumber",)),
        "area": _first(tags, ("addr:suburb", "addr:neighbourhood")),
        "city": _first(tags, ("addr:city", "addr:town", "addr:village")),
        "district": _first(tags, ("addr:district", "addr:county")),
        "state": _first(tags, ("addr:state", "addr:province")),
        "country": _first(tags, ("addr:country",)),
        "postal_code": _first(tags, ("addr:postcode",)),
        "phone": _first(tags, _PHONE_KEYS),
        "mobile": _first(tags, _MOBILE_KEYS),
        "website": _first(tags, _WEBSITE_KEYS),
        "email": _first(tags, _EMAIL_KEYS),
        "opening_hours": _first(tags, ("opening_hours",)),
        "operator": _first(tags, ("operator",)),
        "brand": _first(tags, ("brand",)),
        "wheelchair": _first(tags, ("wheelchair",)),
        "payment_methods": payment_methods(tags),
        "social": social_links(tags),
    }


def element_coordinates(element: dict) -> tuple[float | None, float | None]:
    """Coordinates of an Overpass element.

    Nodes carry `lat`/`lon` directly. Ways and relations do not — with
    `out center` Overpass supplies a `center` object instead, and reading only
    `lat`/`lon` silently drops every non-node result (which is most buildings).
    """
    lat = element.get("lat")
    lon = element.get("lon")
    if lat is None or lon is None:
        centre = element.get("center") or {}
        lat, lon = centre.get("lat"), centre.get("lon")
    return _as_float(lat), _as_float(lon)


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
