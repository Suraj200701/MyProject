"""Provider credential management — write-only storage, encrypted at rest.

The invariant these protect: an operator can configure a provider from the API
Manager without a redeploy, and no endpoint ever hands the stored value back.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update

from models.search import ApiProvider
from services.providers import mappls, registry
from utils import crypto

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _provider_id(db_session, name: str):
    stmt = select(ApiProvider).where(ApiProvider.name == name)
    return (await db_session.execute(stmt)).scalar_one().id


async def _row(db_session, provider_id) -> ApiProvider:
    db_session.expire_all()
    stmt = select(ApiProvider).where(ApiProvider.id == provider_id)
    return (await db_session.execute(stmt)).scalar_one()


@pytest_asyncio.fixture(autouse=True)
async def _reset_provider_credentials(db_session):
    """Clears stored credentials before each test in this module.

    `conftest._clean_tables` deliberately keeps `api_providers` — it is seeded
    reference data. But the credential columns on those rows are mutable state
    that a test writes, so without this a test asserting "nothing is configured"
    sees whatever the previous test saved.
    """
    await db_session.execute(
        update(ApiProvider).values(api_key_encrypted=None, api_secret_encrypted=None, connected=False)
    )
    await db_session.commit()
    yield


@pytest_asyncio.fixture
async def encryption_configured(monkeypatch):
    """A real Fernet keyring for the duration of one test.

    `_get_multi_fernet` is lru_cached on the key tuple, so the cache is cleared
    on both sides — otherwise a later test inherits this key.
    """
    monkeypatch.setattr(
        crypto.settings,
        "PROVIDER_CREDENTIAL_ENCRYPTION_KEY",
        crypto.generate_key(),
        raising=False,
    )
    crypto._get_multi_fernet.cache_clear()
    yield
    crypto._get_multi_fernet.cache_clear()


async def test_credentials_are_never_returned_by_the_api(
    client: AsyncClient, signed_up_user, db_session, encryption_configured
):
    """The whole point: a stored secret must not be readable back out."""
    _, headers = signed_up_user
    provider_id = await _provider_id(db_session, "Mappls (MapmyIndia)")

    resp = await client.put(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=headers,
        json={"api_key": "my-client-id", "api_secret": "my-client-secret"},
    )
    assert resp.status_code == 200, resp.text

    assert "my-client-id" not in resp.text
    assert "my-client-secret" not in resp.text

    body = resp.json()
    assert body["source"] == "workspace"
    assert body["key"]["is_set"] is True
    assert body["secret"]["is_set"] is True

    listing = await client.get("/api/v1/providers/credentials", headers=headers)
    assert listing.status_code == 200
    assert "my-client-secret" not in listing.text


async def test_stored_credentials_are_encrypted_at_rest(
    client: AsyncClient, signed_up_user, db_session, encryption_configured
):
    _, headers = signed_up_user
    provider_id = await _provider_id(db_session, "Mappls (MapmyIndia)")

    await client.put(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=headers,
        json={"api_key": "plain-id", "api_secret": "plain-secret"},
    )

    row = await _row(db_session, provider_id)
    assert row.api_key_encrypted and row.api_key_encrypted != "plain-id"
    assert row.api_secret_encrypted and row.api_secret_encrypted != "plain-secret"
    # ...and round-trips back through the keyring.
    assert crypto.decrypt(row.api_key_encrypted) == "plain-id"
    assert crypto.decrypt(row.api_secret_encrypted) == "plain-secret"


async def test_stored_credentials_reach_the_adapter(
    client: AsyncClient, signed_up_user, db_session, encryption_configured, monkeypatch
):
    """The stored pair must be what Mappls actually authenticates with.

    The registry previously discarded the row's credentials for Mappls, so
    saving them would have changed nothing.
    """
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_ID", "", raising=False)
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_SECRET", "", raising=False)

    _, headers = signed_up_user
    provider_id = await _provider_id(db_session, "Mappls (MapmyIndia)")
    await client.put(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=headers,
        json={"api_key": "row-id", "api_secret": "row-secret"},
    )

    adapter = registry.build_adapter(await _row(db_session, provider_id))
    assert adapter.is_configured, "an empty environment must not stop stored credentials working"
    assert adapter._client.client_id == "row-id"
    assert adapter._client.client_secret == "row-secret"


async def test_clearing_credentials_falls_back_to_the_environment(
    client: AsyncClient, signed_up_user, db_session, encryption_configured, monkeypatch
):
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_ID", "env-id", raising=False)
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_SECRET", "env-secret", raising=False)

    _, headers = signed_up_user
    provider_id = await _provider_id(db_session, "Mappls (MapmyIndia)")
    await client.put(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=headers,
        json={"api_key": "row-id", "api_secret": "row-secret"},
    )

    resp = await client.delete(f"/api/v1/providers/{provider_id}/credentials", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["source"] == "environment"

    row = await _row(db_session, provider_id)
    assert row.api_key_encrypted is None and row.api_secret_encrypted is None
    assert registry.build_adapter(row)._client.client_id == "env-id"


async def test_partial_update_leaves_the_other_field_alone(
    client: AsyncClient, signed_up_user, db_session, encryption_configured
):
    """Rotating a secret must not require re-entering the client id."""
    _, headers = signed_up_user
    provider_id = await _provider_id(db_session, "Mappls (MapmyIndia)")
    await client.put(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=headers,
        json={"api_key": "keep-me", "api_secret": "old-secret"},
    )
    await client.put(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=headers,
        json={"api_secret": "new-secret"},
    )

    row = await _row(db_session, provider_id)
    assert crypto.decrypt(row.api_key_encrypted) == "keep-me"
    assert crypto.decrypt(row.api_secret_encrypted) == "new-secret"


async def test_refuses_to_store_when_encryption_is_unconfigured(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    """Writing plaintext into a column named *_encrypted is worse than failing."""
    monkeypatch.setattr(crypto.settings, "PROVIDER_CREDENTIAL_ENCRYPTION_KEY", "", raising=False)
    crypto._get_multi_fernet.cache_clear()

    _, headers = signed_up_user
    provider_id = await _provider_id(db_session, "Mappls (MapmyIndia)")
    resp = await client.put(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=headers,
        json={"api_key": "should-not-persist"},
    )
    assert resp.status_code == 400
    assert "PROVIDER_CREDENTIAL_ENCRYPTION_KEY" in resp.json()["message"]

    assert (await _row(db_session, provider_id)).api_key_encrypted is None


async def test_provider_without_a_credential_spec_is_rejected(
    client: AsyncClient, signed_up_user, db_session, encryption_configured
):
    _, headers = signed_up_user
    provider_id = await _provider_id(db_session, "Company Website Search")
    resp = await client.put(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=headers,
        json={"api_key": "irrelevant"},
    )
    assert resp.status_code == 400
    assert "does not take credentials" in resp.json()["message"]


async def test_single_credential_provider_rejects_a_secret(
    client: AsyncClient, signed_up_user, db_session, encryption_configured
):
    _, headers = signed_up_user
    provider_id = await _provider_id(db_session, "Google Places")
    resp = await client.put(
        f"/api/v1/providers/{provider_id}/credentials",
        headers=headers,
        json={"api_key": "k", "api_secret": "unexpected"},
    )
    assert resp.status_code == 400
    assert "single credential" in resp.json()["message"]


async def test_empty_update_is_rejected(
    client: AsyncClient, signed_up_user, db_session, encryption_configured
):
    _, headers = signed_up_user
    provider_id = await _provider_id(db_session, "Google Places")
    resp = await client.put(
        f"/api/v1/providers/{provider_id}/credentials", headers=headers, json={}
    )
    assert resp.status_code == 400


async def test_status_reports_unset_when_nothing_is_configured(
    client: AsyncClient, signed_up_user, db_session, monkeypatch
):
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_ID", "", raising=False)
    monkeypatch.setattr(mappls.settings, "MAPPLS_CLIENT_SECRET", "", raising=False)

    _, headers = signed_up_user
    resp = await client.get("/api/v1/providers/credentials", headers=headers)
    assert resp.status_code == 200

    by_name = {entry["name"]: entry for entry in resp.json()}
    assert by_name["Mappls (MapmyIndia)"]["source"] == "unset"
    # A provider that needs no credentials is reported as such, not as broken.
    assert by_name["Company Website Search"]["source"] == "none_required"
    assert by_name["Company Website Search"]["key"] is None
