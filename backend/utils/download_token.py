"""Short-lived signed tokens for export downloads.

Why this exists
---------------
`GET /exports/{id}/download` normally authenticates with `Authorization: Bearer
<access_token>`, which is right for scripts and for `fetch()`. But a browser
cannot attach a header to a plain navigation — `<a href="...">Download</a>`,
`window.open`, and the native download manager all send a bare GET. The usual
workarounds are worse than a signed URL:

* Putting the access token in the query string leaks a **long-lived,
  full-privilege** credential into browser history, proxy logs and `Referer`
  headers.
* Fetching the file into memory and using a Blob URL breaks streaming and falls
  over on large exports.

So the client asks for a token scoped to *one export*, for *one user*, valid for
minutes, and uses that in the URL. If it leaks, the blast radius is one already-
generated file for a few minutes — not the account.

Design
------
* **HMAC-SHA256 over `export_id:user_id:expiry`**, keyed by `JWT_SECRET_KEY`.
  Nothing new to configure and nothing new to rotate.
* **Domain separation.** The payload is prefixed with a constant context string
  before signing, so a token minted here can never be replayed as a signature
  for some other feature that HMACs the same secret.
* **Constant-time comparison** via `hmac.compare_digest`, so a forged signature
  cannot be recovered byte-by-byte from response timing.
* **Expiry is inside the signed payload**, not alongside it — a client cannot
  extend its own token's life.
* The token authorizes *reading one export*. The download route still re-checks
  that the export exists, belongs to the caller's organization, is READY, and has
  not passed its own retention expiry. A valid signature is not a bypass.

Deliberately not JWT: this needs no claims negotiation, no algorithm agility and
no key discovery, and keeping it out of `auth/` means the authentication module
is untouched by the Export Center.
"""

from __future__ import annotations

import base64
import hmac
import time
import uuid
from hashlib import sha256

from config.settings import settings

# Bound into every signature so these tokens are only ever valid as export
# download tokens. Changing this string invalidates all outstanding tokens.
_CONTEXT = b"leadmaster.export.download.v1"

# Guards against a pathological input reaching the parser at all.
_MAX_TOKEN_LENGTH = 512


class DownloadTokenError(Exception):
    """Token missing, malformed, tampered with, or expired.

    One exception for every failure mode on purpose: telling a caller whether a
    token was *expired* versus *forged* tells an attacker which half of the token
    to keep working on.
    """


def _b64encode(raw: bytes) -> str:
    # URL-safe and unpadded: the token travels in a query string, where "+", "/"
    # and "=" all need escaping and frequently get mangled by intermediaries.
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(payload: bytes) -> str:
    key = settings.JWT_SECRET_KEY.encode("utf-8")
    return _b64encode(hmac.new(key, _CONTEXT + b"|" + payload, sha256).digest())


def issue(export_id: uuid.UUID, user_id: uuid.UUID, ttl_seconds: int | None = None) -> tuple[str, int]:
    """Mints a token for one export and one user.

    Returns `(token, expires_in_seconds)` so the caller can tell the client how
    long it has without parsing the token back.
    """
    ttl = ttl_seconds if ttl_seconds is not None else settings.EXPORT_DOWNLOAD_TOKEN_TTL_SECONDS
    ttl = max(1, int(ttl))
    expiry = int(time.time()) + ttl

    payload = f"{export_id}:{user_id}:{expiry}".encode("utf-8")
    return f"{_b64encode(payload)}.{_sign(payload)}", ttl


def verify(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Validates a token and returns `(export_id, user_id)`.

    Raises `DownloadTokenError` for anything that is not a currently-valid token.
    """
    if not token or len(token) > _MAX_TOKEN_LENGTH:
        raise DownloadTokenError("Invalid download token")

    encoded_payload, separator, signature = token.partition(".")
    if not separator or not encoded_payload or not signature:
        raise DownloadTokenError("Invalid download token")

    # Verify the signature BEFORE parsing the payload, so unauthenticated bytes
    # never reach the UUID/int parsers.
    try:
        payload = _b64decode(encoded_payload)
    except (ValueError, TypeError) as exc:
        raise DownloadTokenError("Invalid download token") from exc

    if not hmac.compare_digest(_sign(payload), signature):
        raise DownloadTokenError("Invalid download token")

    try:
        export_id_raw, user_id_raw, expiry_raw = payload.decode("utf-8").split(":")
        export_id = uuid.UUID(export_id_raw)
        user_id = uuid.UUID(user_id_raw)
        expiry = int(expiry_raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise DownloadTokenError("Invalid download token") from exc

    if expiry < time.time():
        raise DownloadTokenError("Invalid download token")

    return export_id, user_id
