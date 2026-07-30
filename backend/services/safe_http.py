"""Hardened outbound HTTP fetch for user-supplied URLs.

This is the only path the website scanner should ever use to reach the
internet. It exists as a separate module (rather than inline in the scanner)
so the safety properties are testable in isolation and can't be quietly
bypassed by a future caller reaching for `httpx` directly.

Guarantees
----------
* **Every URL is validated before connecting** via `utils.url_guard`
  (scheme/port/hostname policy + DNS resolution + IP-range checks).
* **Redirects are followed manually, one hop at a time**, and each hop is
  re-validated. `httpx`'s own `follow_redirects=True` is deliberately NOT
  used: it would follow a 302 into `169.254.169.254` without consulting the
  guard. This is the single most important behaviour in this file.
* **Response size is capped while streaming.** The body is read in chunks and
  aborted the moment the cap is exceeded, so a multi-GB response can't
  exhaust memory — checking `Content-Length` alone is insufficient because
  it is attacker-controlled and optional.
* **Connect and total timeouts** are enforced separately, so a host that
  accepts the TCP connection then stalls cannot hold a worker indefinitely.
* **Identifiable User-Agent** with a contact URL, so site operators can
  attribute and block the crawler if they wish.

Not yet implemented (documented, not silently missing)
------------------------------------------------------
* **IP pinning.** `ValidatedUrl.resolved_ips` is available but the connection
  still re-resolves, leaving a narrow DNS-rebinding window (see the module
  docstring in `utils/url_guard.py`). Closing it needs a custom transport.
* **robots.txt.** Not consulted here. Whether to honour it is a policy
  decision for the caller; see the migration plan's legal/ethical section.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from config.settings import settings
from utils.exceptions import UnsafeUrlError
from utils.url_guard import ValidatedUrl, resolve_and_validate

logger = logging.getLogger("leadmaster.safe_http")

_CHUNK_SIZE = 64 * 1024
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class FetchError(Exception):
    """Fetch failed for a non-security reason (DNS, TLS, timeout, HTTP error).

    Kept distinct from `UnsafeUrlError` so callers can tell "we refused to
    fetch this" (a 400 to the user) apart from "we tried and it didn't work"
    (a scan result recording the failure).
    """

    def __init__(self, message: str, *, kind: str = "network"):
        super().__init__(message)
        self.kind = kind


@dataclass
class FetchResult:
    """Outcome of a successful fetch."""

    final_url: str
    status_code: int
    content: bytes
    headers: dict[str, str]
    elapsed_ms: int
    redirect_chain: list[str] = field(default_factory=list)
    truncated: bool = False
    tls_used: bool = False

    @property
    def text(self) -> str:
        """Body decoded as text, tolerating malformed bytes.

        Real-world pages routinely mis-declare their charset; `errors="replace"`
        keeps extraction working instead of throwing on one bad byte.
        """
        encoding = "utf-8"
        content_type = self.headers.get("content-type", "")
        if "charset=" in content_type:
            encoding = content_type.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            return self.content.decode(encoding, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(
        settings.SCANNER_TIMEOUT_SECONDS,
        connect=settings.SCANNER_CONNECT_TIMEOUT_SECONDS,
    )


def _headers() -> dict[str, str]:
    return {
        "User-Agent": settings.SCANNER_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en",
        # Identity encoding keeps the streaming byte cap meaningful — a
        # compressed body could otherwise expand past the limit after decoding.
        "Accept-Encoding": "identity",
    }


async def _read_capped(response: httpx.Response, max_bytes: int) -> tuple[bytes, bool]:
    """Streams the body, stopping at `max_bytes`. Returns (body, truncated)."""
    buffer = bytearray()
    truncated = False
    async for chunk in response.aiter_bytes(_CHUNK_SIZE):
        remaining = max_bytes - len(buffer)
        if remaining <= 0:
            truncated = True
            break
        if len(chunk) > remaining:
            buffer.extend(chunk[:remaining])
            truncated = True
            break
        buffer.extend(chunk)
    return bytes(buffer), truncated


async def safe_fetch(
    raw_url: str,
    *,
    max_bytes: int | None = None,
    max_redirects: int | None = None,
) -> FetchResult:
    """Validates and fetches a user-supplied URL.

    Raises:
        UnsafeUrlError: the URL (or a redirect target) failed the SSRF guard.
        FetchError: the request was permitted but failed to complete.
    """
    max_bytes = max_bytes if max_bytes is not None else settings.SCANNER_MAX_PAGE_BYTES
    max_redirects = max_redirects if max_redirects is not None else settings.SCANNER_MAX_REDIRECTS

    validated: ValidatedUrl = await resolve_and_validate(raw_url)
    current_url = validated.url
    redirect_chain: list[str] = []

    # follow_redirects is False by design — see module docstring.
    async with httpx.AsyncClient(
        timeout=_timeout(),
        follow_redirects=False,
        headers=_headers(),
        # Cap concurrent sockets so one scan can't monopolise the pool.
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=0),
    ) as client:
        for hop in range(max_redirects + 1):
            try:
                request = client.build_request("GET", current_url)
                response = await client.send(request, stream=True)
            except httpx.TimeoutException as exc:
                raise FetchError(
                    f"Request timed out after {settings.SCANNER_TIMEOUT_SECONDS}s", kind="timeout"
                ) from exc
            except httpx.TooManyRedirects as exc:  # pragma: no cover - manual redirects
                raise FetchError("Too many redirects", kind="redirect") from exc
            except httpx.ConnectError as exc:
                raise FetchError("Could not connect to the host", kind="connect") from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"Request failed: {type(exc).__name__}", kind="network") from exc

            try:
                if response.status_code in _REDIRECT_STATUSES:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError(
                            f"Redirect ({response.status_code}) with no Location header",
                            kind="redirect",
                        )
                    if hop >= max_redirects:
                        raise FetchError(
                            f"Exceeded the maximum of {max_redirects} redirects", kind="redirect"
                        )

                    # Resolve relative Location values against the current URL,
                    # then re-run the FULL guard on the target. This is the hop
                    # where an SSRF attempt would otherwise slip through.
                    next_url = str(httpx.URL(current_url).join(location))
                    revalidated = await resolve_and_validate(next_url)

                    redirect_chain.append(current_url)
                    current_url = revalidated.url
                    continue

                content, truncated = await _read_capped(response, max_bytes)
            finally:
                await response.aclose()

            elapsed_ms = int(response.elapsed.total_seconds() * 1000) if response.elapsed else 0

            if truncated:
                logger.info("Truncated %s at %s bytes", current_url, max_bytes)

            return FetchResult(
                final_url=current_url,
                status_code=response.status_code,
                content=content,
                headers={k.lower(): v for k, v in response.headers.items()},
                elapsed_ms=elapsed_ms,
                redirect_chain=redirect_chain,
                truncated=truncated,
                tls_used=current_url.startswith("https://"),
            )

    # Unreachable: the loop either returns or raises.
    raise FetchError("Fetch did not complete", kind="unknown")  # pragma: no cover


async def check_url_reachable(raw_url: str) -> tuple[bool, str | None]:
    """Validate-and-probe helper. Returns (ok, error_message).

    Convenience for callers that want to surface a reachability problem
    without treating it as an exception — e.g. recording a failed scan row.
    """
    try:
        result = await safe_fetch(raw_url)
        return 200 <= result.status_code < 400, None
    except UnsafeUrlError as exc:
        return False, str(exc.detail)
    except FetchError as exc:
        return False, str(exc)
