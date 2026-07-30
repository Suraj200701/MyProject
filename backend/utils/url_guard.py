"""SSRF protection and URL validation for user-supplied scan targets.

Why this module exists
----------------------
The website scanner accepts a URL from an authenticated caller and (once real
fetching lands) retrieves it *from the server*. Without hardening, that endpoint
is a server-side request forgery primitive: a caller could aim it at cloud
instance metadata (`169.254.169.254`, which hands out IAM credentials on AWS/GCP/
Azure), at this API's own admin surface via `localhost`, or at any RFC-1918 host
reachable from the app's network segment.

Defence in depth — the layers, in order
---------------------------------------
1. **Syntactic validation** — scheme allowlist (`http`/`https` only), no embedded
   credentials, no whitespace/control characters, sane length, port allowlist.
2. **Hostname rules** — reject `localhost`, internal-only suffixes (`.local`,
   `.internal`, `.localdomain`, …), bare IPs that are already private, plus any
   operator-configured blocked domains.
3. **DNS resolution + IP inspection** — resolve the hostname and check *every*
   returned address (A and AAAA). This is the layer that actually stops metadata
   and private-range access, because a public hostname can resolve to
   `127.0.0.1` or `169.254.169.254`. Checking the hostname string alone is not
   sufficient and is the most common way SSRF guards are defeated.
4. **Per-redirect revalidation** — a permitted public URL can 302 to an internal
   one, so every hop is re-checked by the caller (see `services/safe_http.py`).

Known residual risk: DNS rebinding
----------------------------------
Between our `getaddrinfo()` check and the HTTP client's own connection, a
hostile DNS server with a ~0 TTL can return a different address (TOCTOU). Fully
closing this requires pinning the connection to the validated IP and sending the
original `Host` header. `resolve_and_validate()` therefore *returns* the
validated IPs so a future transport can pin to them, and this limitation is
documented rather than left implicit. For the current threat model — an
authenticated tenant scanning business websites — validation plus per-hop
revalidation is a reasonable posture; pinning is the natural next hardening step.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import anyio

from config.settings import settings
from utils.exceptions import UnsafeUrlError

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = frozenset({"http", "https"})

# Hostnames that must never be resolved, let alone fetched.
BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "broadcasthost",
        # Common cloud metadata hostnames — blocked by name as well as by IP,
        # since name-based access doesn't always require DNS to resolve publicly.
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
    }
)

# Suffixes that only ever denote internal/private namespaces.
BLOCKED_HOST_SUFFIXES = (
    ".local",
    ".localdomain",
    ".internal",
    ".intranet",
    ".private",
    ".corp",
    ".home",
    ".lan",
)

# Cloud metadata service addresses. These fall inside link-local/private ranges
# that `_is_blocked_ip` already rejects, but they're listed explicitly so the
# intent is legible and so removing a range check can't silently unblock them.
CLOUD_METADATA_IPS = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),  # AWS / GCP / Azure / DigitalOcean
        ipaddress.ip_address("169.254.170.2"),  # AWS ECS task metadata
        ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud
        ipaddress.ip_address("192.0.0.192"),  # Oracle Cloud
        ipaddress.ip_address("fd00:ec2::254"),  # AWS IMDS over IPv6
    }
)

# Extra CIDRs not covered by the stdlib `is_private` family.
EXTRA_BLOCKED_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),  # RFC 6598 carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),  # RFC 6890 IETF protocol assignments
    ipaddress.ip_network("198.18.0.0/15"),  # RFC 2544 benchmarking
    ipaddress.ip_network("64:ff9b::/96"),  # NAT64 — can be used to reach IPv4 privates
)

# Control characters and whitespace that enable request smuggling / header
# injection if they survive into the request line.
_FORBIDDEN_CHARS = re.compile(r"[\s\x00-\x1f\x7f]")

# Conservative hostname shape: letters/digits/hyphens per label, dot-separated.
_HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$")


@dataclass(frozen=True)
class ValidatedUrl:
    """Result of a successful validation pass.

    `resolved_ips` is returned so a future IP-pinning transport can connect
    directly to an already-vetted address instead of re-resolving.
    """

    url: str
    scheme: str
    hostname: str
    port: int
    resolved_ips: tuple[str, ...]


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> tuple[bool, str]:
    """Returns (blocked, human-readable reason)."""
    if ip in CLOUD_METADATA_IPS:
        return True, "cloud metadata endpoint"
    if ip.is_loopback:
        return True, "loopback address"
    if ip.is_link_local:
        return True, "link-local address"
    if ip.is_private:
        return True, "private network address"
    if ip.is_multicast:
        return True, "multicast address"
    if ip.is_reserved:
        return True, "reserved address"
    if ip.is_unspecified:
        return True, "unspecified address"
    # IPv4-mapped/compatible IPv6 (::ffff:127.0.0.1) — unwrap and re-check so
    # an IPv6 literal can't smuggle a private IPv4 target past the checks above.
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped or getattr(ip, "sixtofour", None)
        if mapped is not None:
            blocked, reason = _is_blocked_ip(mapped)
            if blocked:
                return True, f"IPv4-mapped {reason}"
    for network in EXTRA_BLOCKED_NETWORKS:
        if ip.version == network.version and ip in network:
            return True, f"address in blocked range {network}"
    return False, ""


def normalize_url(raw: str) -> str:
    """Sanitizes and canonicalizes a user-supplied URL string.

    Adds a default `https://` scheme, strips fragments, lowercases the host,
    and drops any embedded credentials. Raises `UnsafeUrlError` on anything
    structurally unacceptable. Does **no** network I/O.
    """
    if raw is None:
        raise UnsafeUrlError("A URL is required")

    value = raw.strip()
    if not value:
        raise UnsafeUrlError("A URL is required")
    if len(value) > MAX_URL_LENGTH:
        raise UnsafeUrlError(f"URL exceeds the maximum length of {MAX_URL_LENGTH} characters")
    if _FORBIDDEN_CHARS.search(value):
        raise UnsafeUrlError("URL contains whitespace or control characters")

    # Scheme-relative ("//host/path") would otherwise parse with an empty scheme.
    if value.startswith("//"):
        value = f"https:{value}"
    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Only http and https URLs can be scanned (got '{scheme}')")

    # Credentials in the URL are a classic way to confuse parsers about which
    # host is actually being contacted (`https://trusted.com@evil.com/`).
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise UnsafeUrlError("URLs containing credentials cannot be scanned")

    if not parsed.hostname:
        raise UnsafeUrlError("URL is missing a hostname")

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:  # non-numeric or out-of-range port
        raise UnsafeUrlError("URL contains an invalid port") from exc

    hostname = parsed.hostname.lower().rstrip(".")

    # `parsed.hostname` strips the brackets from an IPv6 literal, so they must
    # be restored when rebuilding — otherwise the rebuilt URL re-parses as
    # host+port and raises deep inside urllib (a 500 instead of a clean 400).
    host_for_netloc = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host_for_netloc if parsed.port is None else f"{host_for_netloc}:{parsed.port}"

    # Rebuild from vetted parts: drops fragment, credentials, and any casing
    # weirdness in the host, while preserving path/query verbatim.
    return urlunparse((scheme, netloc, parsed.path or "/", parsed.params, parsed.query, ""))


def validate_url_syntax(raw: str) -> tuple[str, str, int]:
    """Runs `normalize_url` plus hostname/port policy. No network I/O.

    Returns `(normalized_url, hostname, port)`. Safe to call on the request
    path for fast rejection before spending a DNS lookup.
    """
    url = normalize_url(raw)
    # Defensive: any residual parse failure must surface as a 400 from this
    # guard, never as an unhandled ValueError (which would be a 500 and would
    # skip the IP checks below entirely).
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        scheme = parsed.scheme
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeUrlError("URL could not be parsed") from exc

    allow_private = settings.SCANNER_ALLOW_PRIVATE_NETWORKS

    if port not in settings.scanner_allowed_ports_set and not allow_private:
        allowed = ", ".join(str(p) for p in sorted(settings.scanner_allowed_ports_set))
        raise UnsafeUrlError(f"Port {port} is not permitted (allowed: {allowed})")

    if not allow_private:
        if hostname in BLOCKED_HOSTNAMES:
            raise UnsafeUrlError("This hostname cannot be scanned")
        if any(hostname.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES):
            raise UnsafeUrlError("Internal-only hostnames cannot be scanned")
        if "." not in hostname:
            # Single-label hosts are intranet names ("intranet", "router").
            raise UnsafeUrlError("A fully-qualified domain name is required")

    for blocked in settings.scanner_blocked_domains_set:
        if hostname == blocked or hostname.endswith(f".{blocked}"):
            raise UnsafeUrlError("This domain has been blocked by your administrator")

    # A bare IP literal skips DNS entirely, so check it here.
    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if not allow_private:
            blocked, reason = _is_blocked_ip(literal_ip)
            if blocked:
                raise UnsafeUrlError(f"This address cannot be scanned ({reason})")
    elif not _HOSTNAME_RE.match(hostname) and not allow_private:
        raise UnsafeUrlError("Hostname is not a valid domain name")

    return url, hostname, port


def _resolve_sync(hostname: str, port: int) -> list[str]:
    """Blocking DNS resolution — run via a worker thread by the async caller."""
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError("This domain could not be resolved") from exc
    # De-duplicate while preserving order for stable, testable output.
    seen: dict[str, None] = {}
    for info in infos:
        seen.setdefault(info[4][0], None)
    return list(seen)


async def resolve_and_validate(raw: str) -> ValidatedUrl:
    """Full validation: syntax, host policy, DNS, and every resolved IP.

    This is the function the scanner must call before any outbound request,
    and again for every redirect target.
    """
    url, hostname, port = validate_url_syntax(raw)

    if settings.SCANNER_ALLOW_PRIVATE_NETWORKS:
        # Dev-only escape hatch. Still resolves so behaviour matches production
        # in every respect except the IP-range verdict.
        try:
            ips = await anyio.to_thread.run_sync(_resolve_sync, hostname, port)
        except UnsafeUrlError:
            ips = []
        return ValidatedUrl(url=url, scheme=urlparse(url).scheme, hostname=hostname, port=port, resolved_ips=tuple(ips))

    ips = await anyio.to_thread.run_sync(_resolve_sync, hostname, port)
    if not ips:
        raise UnsafeUrlError("This domain could not be resolved")

    for raw_ip in ips:
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            raise UnsafeUrlError("This domain resolved to an unrecognized address") from None
        blocked, reason = _is_blocked_ip(ip)
        if blocked:
            # Deliberately does not echo the resolved IP — otherwise this
            # endpoint becomes an internal-network scanner via error messages.
            raise UnsafeUrlError(f"This domain resolves to a disallowed address ({reason})")

    return ValidatedUrl(
        url=url,
        scheme=urlparse(url).scheme,
        hostname=hostname,
        port=port,
        resolved_ips=tuple(ips),
    )
