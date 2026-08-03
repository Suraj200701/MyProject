"""Credit metering tests — runs against the real test database.

Covers the money-adjacent invariants:
  * a search debits credits and records a CREDIT_USAGE ledger entry
  * an organization without enough credits is refused with 402 and charged nothing
  * over-reservation is refunded so users only pay for real output
  * a failed operation leaves the balance untouched (no double-refund)
  * provider-specific costs are honoured
  * scanner URLs are SSRF-validated before any credit is spent
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from config.settings import Settings
from models.billing import CreditWallet, Transaction
from models.enums import TransactionType
from models.organization import Organization, OrganizationMember
from models.search import ApiProvider
from models.user import User
from services import usage_service
from utils.exceptions import InsufficientCreditsError

# The pure cost-calculation tests below are synchronous; a module-level
# asyncio mark would make pytest-asyncio mishandle them, so async tests
# are marked individually (same approach as tests/test_url_guard.py).
asyncio_test = pytest.mark.asyncio(loop_scope="session")


async def _org_id(session, headers) -> uuid.UUID:
    """The signup fixture creates exactly one org; grab the newest."""
    stmt = select(Organization).order_by(Organization.created_at.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one().id


async def _balance(session, org_id: uuid.UUID) -> int:
    return (
        await session.execute(select(CreditWallet.balance).where(CreditWallet.organization_id == org_id))
    ).scalar_one()


async def _set_balance(session, org_id: uuid.UUID, value: int) -> None:
    wallet = (
        await session.execute(select(CreditWallet).where(CreditWallet.organization_id == org_id))
    ).scalar_one()
    wallet.balance = value
    await session.commit()


async def _promote_to_superadmin(session, org_id: uuid.UUID) -> None:
    """Flags the organization's member as a platform superadmin."""
    user_id = (
        await session.execute(
            select(OrganizationMember.user_id).where(OrganizationMember.organization_id == org_id)
        )
    ).scalars().first()
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    user.is_superadmin = True
    await session.commit()


# --- Cost calculation (pure, no DB) ---------------------------------------


def test_estimate_uses_per_provider_cost():
    providers = [
        ApiProvider(name="Cheap", credit_cost=1),
        ApiProvider(name="Pricey", credit_cost=5),
    ]
    # 2 providers x cap of 10 results, priced 1 and 5 -> 10 + 50
    assert usage_service.estimate_search_cost(providers, max_results_per_provider=10) == 60


def test_estimate_falls_back_to_default_when_cost_is_null():
    providers = [ApiProvider(name="Unpriced", credit_cost=None)]
    estimate = usage_service.estimate_search_cost(providers, max_results_per_provider=4)
    assert estimate == 4 * usage_service.settings.DEFAULT_SEARCH_CREDIT_COST_PER_RESULT


def test_zero_cost_provider_is_free():
    providers = [ApiProvider(name="Enrichment only", credit_cost=0)]
    assert usage_service.estimate_search_cost(providers, max_results_per_provider=50) == 0


def test_actual_cost_prices_each_provider_separately():
    cheap = ApiProvider(name="Cheap", credit_cost=1)
    cheap.id = uuid.uuid4()
    pricey = ApiProvider(name="Pricey", credit_cost=4)
    pricey.id = uuid.uuid4()
    counts = {cheap.id: 3, pricey.id: 2}
    assert usage_service.calculate_search_actual_cost(counts, [cheap, pricey]) == 3 * 1 + 2 * 4


# --- reserve / settle / release (DB) --------------------------------------


@asyncio_test
async def test_reserve_debits_and_writes_ledger_entry(client: AsyncClient, signed_up_user, db_session):
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 100)

    reservation = await usage_service.reserve_credits(db_session, org_id, 30, "test op")
    await db_session.commit()

    assert reservation.amount == 30
    assert await _balance(db_session, org_id) == 70

    entries = (
        await db_session.execute(
            select(Transaction).where(
                Transaction.organization_id == org_id,
                Transaction.type == TransactionType.CREDIT_USAGE,
            )
        )
    ).scalars().all()
    assert len(entries) == 1
    assert entries[0].credits_delta == -30
    assert entries[0].balance_after == 70


@asyncio_test
async def test_reserve_raises_402_when_insufficient(client: AsyncClient, signed_up_user, db_session):
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 5)

    with pytest.raises(InsufficientCreditsError) as exc:
        await usage_service.reserve_credits(db_session, org_id, 50, "too expensive")

    assert exc.value.status_code == 402
    assert exc.value.required == 50
    assert exc.value.available == 5
    # Nothing consumed, and no ledger noise from the rejected attempt.
    await db_session.rollback()
    assert await _balance(db_session, org_id) == 5


@asyncio_test
async def test_settle_refunds_the_unused_portion(client: AsyncClient, signed_up_user, db_session):
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 100)

    reservation = await usage_service.reserve_credits(db_session, org_id, 40, "search")
    assert await _balance(db_session, org_id) == 60

    charged = await usage_service.settle_reservation(db_session, reservation, actual_amount=12)
    await db_session.commit()

    assert charged == 12
    assert await _balance(db_session, org_id) == 88  # 100 - 12


@asyncio_test
async def test_settle_is_idempotent(client: AsyncClient, signed_up_user, db_session):
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 50)

    reservation = await usage_service.reserve_credits(db_session, org_id, 20, "op")
    await usage_service.settle_reservation(db_session, reservation, actual_amount=5)
    balance_after_first = await _balance(db_session, org_id)

    # A second settle must not move the balance again.
    await usage_service.settle_reservation(db_session, reservation, actual_amount=5)
    await db_session.commit()
    assert await _balance(db_session, org_id) == balance_after_first


@asyncio_test
async def test_release_refunds_in_full(client: AsyncClient, signed_up_user, db_session):
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 70)

    reservation = await usage_service.reserve_credits(db_session, org_id, 25, "will fail")
    assert await _balance(db_session, org_id) == 45

    await usage_service.release_reservation(db_session, reservation, reason="provider down")
    await db_session.commit()
    assert await _balance(db_session, org_id) == 70


@asyncio_test
async def test_metering_disabled_is_a_noop(client: AsyncClient, signed_up_user, db_session, monkeypatch):
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 10)

    # CREDIT_METERING_ENABLED is a pydantic field (instance attribute), so it
    # is patched on the settings instance rather than as a class property.
    monkeypatch.setattr(usage_service.settings, "CREDIT_METERING_ENABLED", False)

    reservation = await usage_service.reserve_credits(db_session, org_id, 9999, "huge")
    await db_session.commit()

    assert reservation.amount == 0
    assert reservation.is_active is False
    assert await _balance(db_session, org_id) == 10  # untouched


# --- End-to-end through the API ------------------------------------------


@asyncio_test
async def test_search_debits_credits(
    client: AsyncClient, signed_up_user, db_session, google_places_configured
):
    """A search that actually sources leads consumes credits and is ledgered.

    This needs a configured provider. It used to pass without one only because
    the search service synthesized leads from a static pool; now that the
    generator is gone, an unconfigured search legitimately costs nothing (see
    test_unconfigured_search_costs_nothing below).
    """
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 5000)

    before = await _balance(db_session, org_id)
    resp = await client.post("/api/v1/search", headers=headers, json={"query": "Panel Builders in Pune"})
    assert resp.status_code == 201
    assert resp.json()["results_count"] > 0

    db_session.expire_all()
    after = await _balance(db_session, org_id)
    assert after < before, "a completed search must consume credits"

    # And it must be recorded in the ledger.
    count = (
        await db_session.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.organization_id == org_id,
                Transaction.type == TransactionType.CREDIT_USAGE,
            )
        )
    ).scalar_one()
    assert count >= 1


@asyncio_test
async def test_unconfigured_search_costs_nothing(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    """Providers without credentials are excluded before the reservation.

    So a search that cannot possibly source anything is free rather than
    charging for calls that were never made.
    """
    from services.providers import google_places, mappls, website_search

    monkeypatch.setattr(google_places.settings, "GOOGLE_MAPS_API_KEY", "", raising=False)
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_ID", "", raising=False)
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_SECRET", "", raising=False)
    monkeypatch.setattr(google_places.settings, "BING_SEARCH_API_KEY", "", raising=False)
    monkeypatch.setattr(website_search.settings, "SCANNER_ENABLED", False, raising=False)

    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 500)

    before = await _balance(db_session, org_id)
    resp = await client.post("/api/v1/search", headers=headers, json={"query": "Panel Builders in Pune"})
    assert resp.status_code == 201
    assert resp.json()["results_count"] == 0

    db_session.expire_all()
    assert await _balance(db_session, org_id) == before


@asyncio_test
async def test_search_blocked_with_402_when_out_of_credits(client: AsyncClient, signed_up_user, db_session):
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 0)

    resp = await client.post("/api/v1/search", headers=headers, json={"query": "Expensive search"})
    assert resp.status_code == 402
    assert "insufficient credits" in resp.json()["message"].lower()

    # A refused search must not have created a Search row.
    history = await client.get("/api/v1/search/history", headers=headers)
    assert history.json()["meta"]["total_items"] == 0


@asyncio_test
async def test_scan_debits_credits(client: AsyncClient, signed_up_user, db_session, monkeypatch):
    """Scan a public-looking domain with DNS stubbed to a public IP."""
    from utils import url_guard

    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["93.184.216.34"])

    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 100)

    resp = await client.post("/api/v1/scan-website", headers=headers, json={"url": "example.com"})
    assert resp.status_code == 201

    db_session.expire_all()
    assert await _balance(db_session, org_id) == 100 - usage_service.scan_cost()


@asyncio_test
async def test_scan_blocked_with_402_when_out_of_credits(client: AsyncClient, signed_up_user, db_session, monkeypatch):
    from utils import url_guard

    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["93.184.216.34"])

    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 0)

    resp = await client.post("/api/v1/scan-website", headers=headers, json={"url": "example.com"})
    assert resp.status_code == 402


# --- Scanner SSRF enforcement at the API boundary -------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://192.168.1.1/admin",
        "file:///etc/passwd",
        "http://db.internal/",
        "http://example.com:22/",
    ],
)
@asyncio_test
async def test_scan_rejects_unsafe_urls_with_400(client: AsyncClient, signed_up_user, url):
    _, headers = signed_up_user
    resp = await client.post("/api/v1/scan-website", headers=headers, json={"url": url})
    assert resp.status_code == 400, f"{url} should have been refused"


@asyncio_test
async def test_unsafe_scan_url_costs_nothing(client: AsyncClient, signed_up_user, db_session):
    """Validation runs before metering, so a blocked URL is never charged."""
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 50)

    resp = await client.post("/api/v1/scan-website", headers=headers, json={"url": "http://169.254.169.254/"})
    assert resp.status_code == 400

    db_session.expire_all()
    assert await _balance(db_session, org_id) == 50


@asyncio_test
async def test_scan_remains_deterministic_per_domain(client: AsyncClient, signed_up_user, monkeypatch):
    """Preserves the coverage of the pre-existing determinism test.

    `tests/test_search_and_rbac.py::test_website_scan_is_deterministic_per_domain`
    scans `example-corp.com`, a domain that does not resolve. Now that the SSRF
    guard validates DNS before scanning, that input is correctly refused with
    400 — so the assertion is restated here against a resolvable domain (with
    DNS stubbed for hermeticity). The property under test is unchanged: the
    same domain must yield the same generated report.
    """
    from utils import url_guard

    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["93.184.216.34"])

    _, headers = signed_up_user
    first = await client.post("/api/v1/scan-website", headers=headers, json={"url": "example.com"})
    second = await client.post("/api/v1/scan-website", headers=headers, json={"url": "example.com"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["confidence_score"] == second.json()["confidence_score"]
    assert first.json()["gst_number"] == second.json()["gst_number"]


@asyncio_test
async def test_scan_persists_normalized_url(client: AsyncClient, signed_up_user, db_session, monkeypatch):
    """The stored URL must be the guard's normalized form, not raw input."""
    from utils import url_guard

    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["93.184.216.34"])

    _, headers = signed_up_user
    resp = await client.post("/api/v1/scan-website", headers=headers, json={"url": "HTTP://Example.COM/Path#frag"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["url"] == "http://example.com/Path"
    assert body["domain"] == "example.com"


# --- Superadmin exemption -------------------------------------------------


def test_superadmin_is_exempt_even_when_metering_is_active(monkeypatch):
    """A platform operator must never be blocked by a tenant's wallet."""
    monkeypatch.setattr(usage_service.settings, "CREDIT_METERING_ENABLED", True, raising=False)
    monkeypatch.setattr(usage_service.settings, "ENVIRONMENT", "production", raising=False)

    class Actor:
        def __init__(self, superadmin: bool) -> None:
            self.is_superadmin = superadmin

    assert usage_service.is_metering_exempt(Actor(True)) is True
    assert usage_service.is_metering_exempt(Actor(False)) is False
    # No actor (background job) is NOT exempt — it must still respect the wallet.
    assert usage_service.is_metering_exempt(None) is False


@asyncio_test
async def test_exempt_reservation_never_touches_the_wallet(db_session, signed_up_user):
    """Exemption is total: no balance check, no debit, no ledger row.

    Charging zero would still write a transaction and imply the operator's
    activity was billable to this tenant; skipping outright keeps the customer's
    usage history clean.
    """
    org_id = await _org_id(db_session, None)
    await _set_balance(db_session, org_id, 10)

    reservation = await usage_service.reserve_credits(
        db_session, org_id, 5000, "Superadmin search", exempt=True
    )
    await db_session.commit()

    assert reservation.amount == 0
    assert reservation.is_active is False
    # Balance untouched despite the request being 500x the balance.
    assert await _balance(db_session, org_id) == 10

    ledger = (
        await db_session.execute(
            select(func.count()).select_from(Transaction).where(Transaction.organization_id == org_id)
        )
    ).scalar_one()
    assert ledger == 0


@asyncio_test
async def test_non_exempt_reservation_still_enforces_the_balance(db_session, signed_up_user):
    """The normal path is unchanged by the exemption parameter's existence."""
    org_id = await _org_id(db_session, None)
    await _set_balance(db_session, org_id, 10)

    with pytest.raises(InsufficientCreditsError):
        await usage_service.reserve_credits(db_session, org_id, 5000, "Normal search", exempt=False)

    await db_session.rollback()
    assert await _balance(db_session, org_id) == 10


@asyncio_test
async def test_settle_and_release_are_noops_for_an_exempt_reservation(db_session, signed_up_user):
    """Guards against an exempt run accidentally *crediting* the wallet."""
    org_id = await _org_id(db_session, None)
    await _set_balance(db_session, org_id, 10)

    reservation = await usage_service.reserve_credits(
        db_session, org_id, 5000, "Superadmin search", exempt=True
    )
    assert await usage_service.settle_reservation(db_session, reservation, 4000) == 0
    await usage_service.release_reservation(db_session, reservation, "cleanup")
    await db_session.commit()

    assert await _balance(db_session, org_id) == 10


# --- Development escape hatch ---------------------------------------------


@pytest.mark.parametrize(
    ("environment", "enabled", "disabled_in_dev", "expected"),
    [
        # Production always meters, regardless of the development flag.
        ("production", True, True, True),
        ("production", True, False, True),
        ("staging", True, True, True),
        # The master switch still wins everywhere.
        ("production", False, True, False),
        # Development is exempt by default, but can opt back in.
        ("development", True, True, False),
        ("development", True, False, True),
    ],
)
def test_credit_metering_active_matrix(environment, enabled, disabled_in_dev, expected):
    """The development escape hatch must be unreachable outside development.

    Guards the one thing that would be catastrophic: a config where production
    silently stops charging for billable work.
    """
    settings = Settings(
        ENVIRONMENT=environment,
        CREDIT_METERING_ENABLED=enabled,
        CREDIT_METERING_DISABLED_IN_DEVELOPMENT=disabled_in_dev,
    )
    assert settings.credit_metering_active is expected


def test_metering_inactive_exempts_everyone(monkeypatch):
    """When metering is off globally, every actor is exempt — not just admins."""
    monkeypatch.setattr(usage_service.settings, "CREDIT_METERING_ENABLED", False, raising=False)

    class Actor:
        is_superadmin = False

    assert usage_service.is_metering_exempt(Actor()) is True
    assert usage_service.is_metering_exempt(None) is True


@asyncio_test
async def test_superadmin_search_is_unlimited_end_to_end(
    client: AsyncClient, signed_up_user, db_session, google_places_configured
):
    """A superadmin with a drained wallet still gets a full search.

    The unit tests above cover `reserve_credits(exempt=True)`; this drives the
    real HTTP route to prove the exemption is actually plumbed through the
    endpoint -> search_service -> usage_service chain, not just available in it.
    """
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 0)

    await _promote_to_superadmin(db_session, org_id)

    resp = await client.post("/api/v1/search", headers=headers, json={"query": "Panel Builders in Pune"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["results_count"] > 0, "the search must return real results, not an empty pass-through"

    db_session.expire_all()
    assert await _balance(db_session, org_id) == 0, "balance must not go negative"

    ledger = (
        await db_session.execute(
            select(func.count()).select_from(Transaction).where(Transaction.organization_id == org_id)
        )
    ).scalar_one()
    assert ledger == 0, "an operator's search must not appear in the tenant's billing history"


@asyncio_test
async def test_normal_user_is_still_blocked_when_out_of_credits(
    client: AsyncClient, signed_up_user, db_session, google_places_configured
):
    """The counterpart to the test above: exemption did not leak to everyone.

    Same setup, same zero balance — only `is_superadmin` differs.
    """
    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 0)

    resp = await client.post("/api/v1/search", headers=headers, json={"query": "Panel Builders in Pune"})
    assert resp.status_code == 402, resp.text


@asyncio_test
async def test_superadmin_scan_is_unlimited_end_to_end(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    """The scanner path is exempt too — it reserves separately from search."""
    from utils import url_guard

    monkeypatch.setattr(url_guard, "_resolve_sync", lambda h, p: ["93.184.216.34"])

    _, headers = signed_up_user
    org_id = await _org_id(db_session, headers)
    await _set_balance(db_session, org_id, 0)

    await _promote_to_superadmin(db_session, org_id)

    resp = await client.post("/api/v1/scan-website", headers=headers, json={"url": "example.com"})
    assert resp.status_code == 201, resp.text

    db_session.expire_all()
    assert await _balance(db_session, org_id) == 0
