"""Symmetric field-level encryption for secrets stored in the database.

Used for provider API credentials (`ApiProvider.api_key_encrypted`) and any
other column that must not be readable from a database dump or a backup.

Design notes
------------
* **Fernet** (AES-128-CBC + HMAC-SHA256, from `cryptography`) — authenticated
  encryption, so tampering is detected rather than silently decrypting to
  garbage. Not chosen for novelty: it's the boring, correct default.
* **Key rotation is supported from day one.** `PROVIDER_CREDENTIAL_ENCRYPTION_KEY`
  accepts a comma-separated list, newest first. `MultiFernet` encrypts with the
  first key and attempts decryption with every key, so rotating means prepending
  a new key and leaving the old one in place until `rotate_ciphertext()` has been
  run over stored rows. Dropping an old key before re-encrypting makes that
  data permanently unreadable.
* **Fails loudly when unconfigured.** A missing key raises rather than falling
  back to plaintext — writing plaintext into a column named `_encrypted` would
  be worse than refusing to write at all.
* Ciphertext is returned as `str` (Fernet tokens are URL-safe base64), which
  stores directly in a `Text` column with no encoding dance.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from config.settings import settings


class EncryptionNotConfiguredError(RuntimeError):
    """Raised when encryption is attempted without a configured key."""

    def __init__(self) -> None:
        super().__init__(
            "Field encryption is not configured. Set PROVIDER_CREDENTIAL_ENCRYPTION_KEY "
            'in .env — generate one with: python -c "from cryptography.fernet import '
            'Fernet; print(Fernet.generate_key().decode())"'
        )


class DecryptionError(RuntimeError):
    """Raised when ciphertext cannot be decrypted with any configured key.

    Means one of: the value was encrypted with a key no longer present, the
    ciphertext was corrupted, or it was never valid Fernet output.
    """


def generate_key() -> str:
    """Generates a new Fernet key. Exposed for setup scripts and tests."""
    return Fernet.generate_key().decode()


@lru_cache(maxsize=1)
def _get_multi_fernet(keys_tuple: tuple[str, ...]) -> MultiFernet:
    """Builds (and caches) the MultiFernet for a given key tuple.

    Cached on the key tuple rather than read from settings directly so tests
    can swap keys by passing a different tuple, and so an accidental settings
    reload doesn't silently keep using stale keys.
    """
    try:
        fernets = [Fernet(key.encode()) for key in keys_tuple]
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "PROVIDER_CREDENTIAL_ENCRYPTION_KEY contains an invalid Fernet key. "
            "Each key must be 32 url-safe base64-encoded bytes."
        ) from exc
    return MultiFernet(fernets)


def _cipher() -> MultiFernet:
    keys = settings.encryption_keys_list
    if not keys:
        raise EncryptionNotConfiguredError()
    return _get_multi_fernet(tuple(keys))


def is_configured() -> bool:
    """True when at least one usable encryption key is present.

    Lets callers degrade gracefully (e.g. hide a 'connect provider' action)
    instead of triggering a 500 on a page load.
    """
    if not settings.encryption_keys_list:
        return False
    try:
        _cipher()
        return True
    except RuntimeError:
        return False


def encrypt(plaintext: str) -> str:
    """Encrypts a secret for storage. Raises if encryption is unconfigured."""
    if plaintext is None:
        raise ValueError("Cannot encrypt None")
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypts a stored secret, trying every configured key in turn."""
    if not ciphertext:
        raise ValueError("Cannot decrypt an empty value")
    try:
        return _cipher().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError(
            "Could not decrypt value with any configured key — the key that "
            "encrypted it may have been removed from "
            "PROVIDER_CREDENTIAL_ENCRYPTION_KEY, or the ciphertext is corrupt."
        ) from exc


def encrypt_optional(plaintext: str | None) -> str | None:
    """Nullable-column convenience: passes `None`/empty through untouched."""
    if plaintext is None or plaintext == "":
        return None
    return encrypt(plaintext)


def decrypt_optional(ciphertext: str | None) -> str | None:
    """Nullable-column convenience: passes `None`/empty through untouched."""
    if ciphertext is None or ciphertext == "":
        return None
    return decrypt(ciphertext)


def rotate_ciphertext(ciphertext: str) -> str:
    """Re-encrypts existing ciphertext under the newest key.

    Run this over stored rows after prepending a new key, then retire the old
    key once every row has been rotated. `MultiFernet.rotate` decrypts with any
    known key and re-encrypts with the primary one.
    """
    if not ciphertext:
        raise ValueError("Cannot rotate an empty value")
    try:
        return _cipher().rotate(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("Could not rotate value — no configured key can decrypt it.") from exc


def mask_secret(plaintext: str, visible_suffix: int = 4) -> str:
    """Display helper: `sk_live_abcd1234` -> `sk_live_•••••••••234`.

    For showing a stored credential in a UI without revealing it. Never
    reconstructs the full secret; short values are fully masked.
    """
    if not plaintext:
        return ""
    if len(plaintext) <= visible_suffix:
        return "•" * len(plaintext)
    return "•" * (len(plaintext) - visible_suffix) + plaintext[-visible_suffix:]
