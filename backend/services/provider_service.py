"""Provider credential management.

Why this exists
---------------
`ApiProvider.api_key_encrypted` and the registry's decrypt-and-use path already
existed, but nothing could ever *write* them — so the API Manager's Credentials
tab could only tell the operator to edit `.env` and restart the process. That
made per-workspace credentials an unreachable feature and made adding a provider
a deploy.

Security model
--------------
Credentials are **write-only over the API**. They are encrypted with
`utils.crypto` (Fernet, key rotation supported) before they touch the database,
and no endpoint ever returns them — not even masked. `credential_status()`
reports only *whether* each field is set and where the effective value comes
from, which is all the UI needs to render state.

Refusing to store a credential when encryption is unconfigured is deliberate:
silently writing plaintext into a column named `*_encrypted` would be worse than
failing loudly.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.search import ApiProvider
from services.providers.registry import PROVIDER_CREDENTIAL_SPECS, CredentialSpec
from utils import crypto
from utils.exceptions import BadRequestError, NotFoundError

logger = logging.getLogger("leadmaster.providers.credentials")


@dataclass
class CredentialStatus:
    """What the UI is allowed to know about a provider's credentials."""

    provider_id: uuid.UUID
    name: str
    # None when this provider takes no credentials (e.g. Company Website Search).
    spec: CredentialSpec | None
    has_stored_key: bool
    has_stored_secret: bool
    # True when the platform-wide environment variables are populated.
    has_environment_fallback: bool

    @property
    def source(self) -> str:
        """Where the value the search pipeline will actually use comes from."""
        if self.spec is None:
            return "none_required"
        if self.has_stored_key and (self.spec.secret_label is None or self.has_stored_secret):
            return "workspace"
        if self.has_environment_fallback:
            return "environment"
        return "unset"


async def _get_provider(db: AsyncSession, provider_id: uuid.UUID) -> ApiProvider:
    provider = (
        await db.execute(select(ApiProvider).where(ApiProvider.id == provider_id))
    ).scalar_one_or_none()
    if provider is None:
        raise NotFoundError("Provider not found")
    return provider


def _environment_configured(spec: CredentialSpec | None) -> bool:
    if spec is None:
        return False
    key = bool(getattr(settings, spec.key_env_var, ""))
    if spec.secret_env_var is None:
        return key
    return key and bool(getattr(settings, spec.secret_env_var, ""))


def status_for(provider: ApiProvider) -> CredentialStatus:
    spec = PROVIDER_CREDENTIAL_SPECS.get(provider.name)
    return CredentialStatus(
        provider_id=provider.id,
        name=provider.name,
        spec=spec,
        has_stored_key=bool(provider.api_key_encrypted),
        has_stored_secret=bool(provider.api_secret_encrypted),
        has_environment_fallback=_environment_configured(spec),
    )


async def list_credential_status(db: AsyncSession) -> list[CredentialStatus]:
    providers = (await db.execute(select(ApiProvider).order_by(ApiProvider.name))).scalars().all()
    return [status_for(p) for p in providers]


async def set_credentials(
    db: AsyncSession,
    provider_id: uuid.UUID,
    *,
    api_key: str | None,
    api_secret: str | None,
) -> CredentialStatus:
    """Encrypts and stores credentials for one provider.

    Passing `None` for a field leaves the stored value untouched, so an operator
    can rotate just the secret of a pair without re-entering the id.
    """
    provider = await _get_provider(db, provider_id)
    spec = PROVIDER_CREDENTIAL_SPECS.get(provider.name)

    if spec is None:
        raise BadRequestError(
            f"'{provider.name}' does not take credentials — it is not a credentialed lead source."
        )

    if not crypto.is_configured():
        raise BadRequestError(
            "Cannot store credentials: PROVIDER_CREDENTIAL_ENCRYPTION_KEY is not set on the "
            "backend. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and restart the API."
        )

    if api_key is None and api_secret is None:
        raise BadRequestError("Provide at least one credential value to store.")

    if api_secret is not None and spec.secret_label is None:
        raise BadRequestError(f"'{provider.name}' takes a single credential, not a pair.")

    if api_key is not None:
        provider.api_key_encrypted = crypto.encrypt(api_key.strip())
    if api_secret is not None:
        provider.api_secret_encrypted = crypto.encrypt(api_secret.strip())

    # `connected` is the flag the provider grid renders. It tracks whether this
    # workspace supplied its own credentials, which is exactly what the operator
    # just changed.
    status = status_for(provider)
    provider.connected = status.source == "workspace"

    await db.flush()
    logger.info(
        "Stored %s credential(s) for provider %s",
        "key+secret" if api_key and api_secret else "key" if api_key else "secret",
        provider.name,
    )
    return status_for(provider)


async def clear_credentials(db: AsyncSession, provider_id: uuid.UUID) -> CredentialStatus:
    """Removes stored credentials, falling back to the environment variables."""
    provider = await _get_provider(db, provider_id)
    provider.api_key_encrypted = None
    provider.api_secret_encrypted = None
    provider.connected = False
    await db.flush()
    logger.info("Cleared stored credentials for provider %s", provider.name)
    return status_for(provider)
