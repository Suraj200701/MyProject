"""Field-encryption helper tests (no DB, no network)."""

import pytest
from cryptography.fernet import Fernet

from utils import crypto


def _set_keys(monkeypatch, keys: list[str]) -> None:
    """Points settings at a specific key list and clears the cipher cache."""
    monkeypatch.setattr(
        crypto.settings.__class__,
        "encryption_keys_list",
        property(lambda self: keys),
    )
    crypto._get_multi_fernet.cache_clear()


def test_generate_key_produces_a_usable_fernet_key():
    key = crypto.generate_key()
    assert len(key) == 44  # 32 bytes, url-safe base64
    Fernet(key.encode())  # must not raise


def test_roundtrip(monkeypatch):
    _set_keys(monkeypatch, [crypto.generate_key()])
    secret = "sk_live_super_secret_value"
    assert crypto.decrypt(crypto.encrypt(secret)) == secret


def test_ciphertext_is_not_plaintext(monkeypatch):
    _set_keys(monkeypatch, [crypto.generate_key()])
    secret = "sk_live_abcdef123456"
    assert secret not in crypto.encrypt(secret)


def test_same_plaintext_encrypts_differently_each_time(monkeypatch):
    """Fernet embeds a random IV, so identical inputs must not collide —
    otherwise equal ciphertexts would leak that two rows share a secret."""
    _set_keys(monkeypatch, [crypto.generate_key()])
    assert crypto.encrypt("same") != crypto.encrypt("same")


def test_raises_when_unconfigured(monkeypatch):
    _set_keys(monkeypatch, [])
    with pytest.raises(crypto.EncryptionNotConfiguredError):
        crypto.encrypt("anything")
    assert crypto.is_configured() is False


def test_is_configured_true_with_valid_key(monkeypatch):
    _set_keys(monkeypatch, [crypto.generate_key()])
    assert crypto.is_configured() is True


def test_invalid_key_is_rejected_loudly(monkeypatch):
    _set_keys(monkeypatch, ["not-a-valid-fernet-key"])
    with pytest.raises(RuntimeError, match="invalid Fernet key"):
        crypto.encrypt("x")


def test_tampered_ciphertext_is_detected(monkeypatch):
    """Fernet is authenticated: modified ciphertext must fail, not decrypt
    to garbage."""
    _set_keys(monkeypatch, [crypto.generate_key()])
    token = crypto.encrypt("secret")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(tampered)


def test_decrypt_with_wrong_key_fails(monkeypatch):
    _set_keys(monkeypatch, [crypto.generate_key()])
    token = crypto.encrypt("secret")
    _set_keys(monkeypatch, [crypto.generate_key()])  # unrelated key
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(token)


def test_key_rotation_keeps_old_ciphertext_readable(monkeypatch):
    """The rotation contract: prepend a new key, old values still decrypt."""
    old_key = crypto.generate_key()
    _set_keys(monkeypatch, [old_key])
    token = crypto.encrypt("legacy-secret")

    new_key = crypto.generate_key()
    _set_keys(monkeypatch, [new_key, old_key])  # newest first
    assert crypto.decrypt(token) == "legacy-secret"

    # Rotating re-encrypts under the new primary key...
    rotated = crypto.rotate_ciphertext(token)
    assert rotated != token
    assert crypto.decrypt(rotated) == "legacy-secret"

    # ...so the old key can then be retired.
    _set_keys(monkeypatch, [new_key])
    assert crypto.decrypt(rotated) == "legacy-secret"


def test_optional_helpers_pass_through_empty(monkeypatch):
    _set_keys(monkeypatch, [crypto.generate_key()])
    assert crypto.encrypt_optional(None) is None
    assert crypto.encrypt_optional("") is None
    assert crypto.decrypt_optional(None) is None
    assert crypto.decrypt_optional("") is None
    assert crypto.decrypt_optional(crypto.encrypt_optional("v")) == "v"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("sk_live_abcd1234", "••••••••••••1234"),
        ("abc", "•••"),
        ("", ""),
    ],
)
def test_mask_secret(value, expected):
    assert crypto.mask_secret(value) == expected


def test_mask_never_reveals_more_than_requested():
    masked = crypto.mask_secret("supersecretvalue", visible_suffix=4)
    assert masked.endswith("alue")
    assert "supersecret" not in masked
