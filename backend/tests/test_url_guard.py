"""SSRF guard tests.

These are the security-critical assertions for the scanner. Anything that
loosens `utils/url_guard.py` should fail here first.

Note: tests that must not depend on live DNS monkeypatch the resolver.
Tests of *syntactic* rejection need no network at all.
"""

import ipaddress

import pytest

from utils import url_guard
from utils.exceptions import UnsafeUrlError

# NOTE: no module-level `pytestmark` here — most tests in this file are
# synchronous (the guard's syntax/IP layers do no I/O), and a blanket
# asyncio mark makes pytest-asyncio mishandle them. The few async tests
# are marked individually.
asyncio_test = pytest.mark.asyncio(loop_scope="session")


# --- normalize_url / syntax ------------------------------------------------


def test_adds_https_scheme_when_missing():
    assert url_guard.normalize_url("example.com").startswith("https://example.com")


def test_lowercases_host_and_strips_fragment():
    assert url_guard.normalize_url("HTTPS://Example.COM/Path#frag") == "https://example.com/Path"


def test_preserves_query_string():
    assert url_guard.normalize_url("https://example.com/s?q=1&r=2") == "https://example.com/s?q=1&r=2"


def test_strips_trailing_dot_on_host():
    # "example.com." is a valid FQDN that bypasses naive string blocklists.
    assert url_guard.normalize_url("https://example.com./") == "https://example.com/"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "file:///etc/passwd",
        "gopher://example.com",
        "ftp://example.com",
        "javascript:alert(1)",
        "https://user:pass@example.com",
        "https://trusted.com@evil.com/",
        "https://exa mple.com",
        "https://example.com/\r\nHost: evil",
        "https://example.com:notaport",
    ],
)
def test_rejects_structurally_unsafe_urls(bad):
    with pytest.raises(UnsafeUrlError):
        url_guard.validate_url_syntax(bad)


def test_rejects_overlong_url():
    with pytest.raises(UnsafeUrlError):
        url_guard.normalize_url("https://example.com/" + "a" * 3000)


def test_scheme_relative_url_is_given_a_scheme():
    assert url_guard.normalize_url("//example.com/x") == "https://example.com/x"


# --- hostname policy ------------------------------------------------------


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "instance-data",
        "myapp.local",
        "db.internal",
        "server.corp",
        "printer.lan",
    ],
)
def test_rejects_internal_hostnames(host):
    with pytest.raises(UnsafeUrlError):
        url_guard.validate_url_syntax(f"https://{host}/")


def test_rejects_single_label_hostname():
    with pytest.raises(UnsafeUrlError):
        url_guard.validate_url_syntax("https://intranet/")


def test_rejects_disallowed_port():
    # 22 is not in the default {80, 443} allowlist.
    with pytest.raises(UnsafeUrlError) as exc:
        url_guard.validate_url_syntax("https://example.com:22/")
    assert "not permitted" in str(exc.value.detail)


def test_allows_default_ports():
    for candidate in ("http://example.com/", "https://example.com/", "https://example.com:443/"):
        url, host, port = url_guard.validate_url_syntax(candidate)
        assert host == "example.com"
        assert port in (80, 443)


def test_operator_blocked_domain_is_rejected(monkeypatch):
    monkeypatch.setattr(
        url_guard.settings.__class__,
        "scanner_blocked_domains_set",
        property(lambda self: {"blocked.com"}),
    )
    with pytest.raises(UnsafeUrlError):
        url_guard.validate_url_syntax("https://sub.blocked.com/")


# --- IP literal rejection (no DNS needed) ---------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "0.0.0.0",  # unspecified
        "10.0.0.5",  # RFC1918
        "172.16.31.1",  # RFC1918
        "192.168.1.1",  # RFC1918
        "169.254.169.254",  # AWS/GCP/Azure metadata
        "169.254.170.2",  # ECS task metadata
        "100.100.100.200",  # Alibaba metadata
        "192.0.0.192",  # Oracle metadata
        "100.64.0.1",  # CGNAT
        "198.18.0.1",  # benchmarking range
        "224.0.0.1",  # multicast
    ],
)
def test_rejects_dangerous_ipv4_literals(ip):
    with pytest.raises(UnsafeUrlError):
        url_guard.validate_url_syntax(f"http://{ip}/")


@pytest.mark.parametrize(
    "ip",
    [
        "[::1]",  # loopback
        "[::]",  # unspecified
        "[fc00::1]",  # unique local
        "[fe80::1]",  # link-local
        "[fd00:ec2::254]",  # AWS IMDS v6
        "[::ffff:127.0.0.1]",  # IPv4-mapped loopback
        "[::ffff:169.254.169.254]",  # IPv4-mapped metadata
    ],
)
def test_rejects_dangerous_ipv6_literals(ip):
    with pytest.raises(UnsafeUrlError):
        url_guard.validate_url_syntax(f"http://{ip}/")


def test_ipv4_mapped_private_is_unwrapped_and_blocked():
    """IPv4-mapped IPv6 must not smuggle a private target past the checks.

    Python's ipaddress already reports ::ffff:10.0.0.1 as private, so the
    exact reason string varies — what matters is that it is refused.
    """
    blocked, _reason = url_guard._is_blocked_ip(ipaddress.ip_address("::ffff:10.0.0.1"))
    assert blocked
    blocked_mapped, _ = url_guard._is_blocked_ip(ipaddress.ip_address("::ffff:127.0.0.1"))
    assert blocked_mapped


def test_public_ip_literal_passes_syntax_but_still_needs_dns_stage():
    # 8.8.8.8 is public: syntax stage must not reject it.
    url, host, port = url_guard.validate_url_syntax("http://8.8.8.8/")
    assert host == "8.8.8.8"


# --- DNS stage ------------------------------------------------------------


@asyncio_test
async def test_rejects_public_hostname_resolving_to_loopback(monkeypatch):
    """The core SSRF case: hostname looks fine, DNS points inside."""
    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["127.0.0.1"])
    with pytest.raises(UnsafeUrlError) as exc:
        await url_guard.resolve_and_validate("https://evil.example.com/")
    assert "disallowed address" in str(exc.value.detail)


@asyncio_test
async def test_rejects_hostname_resolving_to_metadata_ip(monkeypatch):
    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["169.254.169.254"])
    with pytest.raises(UnsafeUrlError):
        await url_guard.resolve_and_validate("https://metadata-attack.example.com/")


@asyncio_test
async def test_rejects_when_any_resolved_ip_is_private(monkeypatch):
    """Multi-record DNS: one public + one private must still be refused."""
    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["93.184.216.34", "10.0.0.9"])
    with pytest.raises(UnsafeUrlError):
        await url_guard.resolve_and_validate("https://mixed.example.com/")


@asyncio_test
async def test_error_message_does_not_leak_resolved_ip(monkeypatch):
    """Error text must not turn this endpoint into an internal port scanner."""
    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["10.11.12.13"])
    with pytest.raises(UnsafeUrlError) as exc:
        await url_guard.resolve_and_validate("https://probe.example.com/")
    assert "10.11.12.13" not in str(exc.value.detail)


@asyncio_test
async def test_accepts_public_hostname(monkeypatch):
    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["93.184.216.34"])
    result = await url_guard.resolve_and_validate("example.com")
    assert result.url == "https://example.com/"
    assert result.hostname == "example.com"
    assert result.port == 443
    assert result.resolved_ips == ("93.184.216.34",)


@asyncio_test
async def test_unresolvable_domain_is_rejected(monkeypatch):
    def _boom(host, port):
        raise UnsafeUrlError("This domain could not be resolved")

    monkeypatch.setattr(url_guard, "_resolve_sync", _boom)
    with pytest.raises(UnsafeUrlError):
        await url_guard.resolve_and_validate("https://does-not-exist.example/")
