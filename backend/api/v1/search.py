"""Lead search, provider catalogue, and website scanner endpoints."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.concurrency import run_in_threadpool
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user, require_permission
from database.session import get_db
from models.enums import ProviderStatus
from models.organization import Organization
from models.search import ApiProvider, Search, WebsiteScan
from models.user import User
from redis_cache.client import get_redis
from schemas.lead import LeadOut
from schemas.search import (
    ApiProviderOut,
    ProviderCredentialStatusOut,
    ProviderCredentialUpdate,
    ProviderTestResult,
    SearchCreate,
    SearchOut,
    WebsiteScanCreate,
    WebsiteScanOut,
)
from services import provider_service, provider_test_service, search_service, usage_service
from utils.exceptions import NotFoundError
from utils.pagination import Page, PaginationParams, paginate, pagination_params

router = APIRouter(tags=["Search"])


@router.post("/search", response_model=SearchOut, status_code=201)
async def create_search(
    payload: SearchCreate,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Superadmins and development runs bypass metering entirely — resolved here
    # because this is where the authenticated User is available.
    exempt = usage_service.is_metering_exempt(user)
    search = await search_service.run_search(
        db, organization.id, user.id, payload, metering_exempt=exempt
    )
    return SearchOut(
        id=search.id,
        query=search.query,
        location=search.location,
        status=search.status,
        results_count=search.results_count,
        created_at=search.created_at,
        completed_at=search.completed_at,
        provider_runs=[
            {
                "provider_id": run.provider_id,
                "provider_name": (await db.get(ApiProvider, run.provider_id)).name,
                "status": run.status,
                "results_found": run.results_found,
            }
            for run in search.provider_runs
        ],
    )


@router.get("/search/history", response_model=Page[SearchOut])
async def search_history(
    params: PaginationParams = Depends(pagination_params),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Search).where(Search.organization_id == organization.id).order_by(Search.created_at.desc())
    searches, meta = await paginate(db, stmt, params)
    items = [
        SearchOut(
            id=s.id,
            query=s.query,
            location=s.location,
            status=s.status,
            results_count=s.results_count,
            created_at=s.created_at,
            completed_at=s.completed_at,
        )
        for s in searches
    ]
    return Page(items=items, meta=meta)


@router.get("/providers", response_model=list[ApiProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    providers = (await db.execute(select(ApiProvider).order_by(ApiProvider.name))).scalars().all()
    return providers


def _to_credential_status(status) -> ProviderCredentialStatusOut:
    """`CredentialStatus` -> wire shape. Deliberately carries no secret values."""
    spec = status.spec
    key = None
    secret = None
    if spec is not None:
        key = {
            "label": spec.key_label,
            "env_var": spec.key_env_var,
            "is_set": status.has_stored_key,
        }
        if spec.secret_label is not None:
            secret = {
                "label": spec.secret_label,
                "env_var": spec.secret_env_var,
                "is_set": status.has_stored_secret,
            }
    return ProviderCredentialStatusOut(
        provider_id=status.provider_id,
        name=status.name,
        source=status.source,
        key=key,
        secret=secret,
        help_url=spec.help_url if spec else None,
    )


@router.get("/providers/credentials", response_model=list[ProviderCredentialStatusOut])
async def list_provider_credentials(
    _membership=Depends(require_permission("api_keys.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Which providers have credentials, and where the effective value comes from.

    Returns no credential values — only whether each field is set. Reading this
    requires `api_keys.manage` because the set/unset pattern across providers is
    itself infrastructure information.
    """
    statuses = await provider_service.list_credential_status(db)
    return [_to_credential_status(s) for s in statuses]


@router.put("/providers/{provider_id}/credentials", response_model=ProviderCredentialStatusOut)
async def set_provider_credentials(
    provider_id: uuid.UUID,
    payload: ProviderCredentialUpdate,
    _membership=Depends(require_permission("api_keys.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Stores encrypted credentials for one provider.

    Write-only: the response reports that the values are set, never what they
    are. Omit a field to leave it unchanged, so the secret of a pair can be
    rotated without re-entering the id.
    """
    status = await provider_service.set_credentials(
        db, provider_id, api_key=payload.api_key, api_secret=payload.api_secret
    )
    await db.commit()
    return _to_credential_status(status)


@router.delete("/providers/{provider_id}/credentials", response_model=ProviderCredentialStatusOut)
async def clear_provider_credentials(
    provider_id: uuid.UUID,
    _membership=Depends(require_permission("api_keys.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Removes this workspace's stored credentials, reverting to the `.env` values."""
    status = await provider_service.clear_credentials(db, provider_id)
    await db.commit()
    return _to_credential_status(status)


@router.post("/providers/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider_connection(
    provider_id: uuid.UUID,
    _membership=Depends(require_permission("api_keys.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Performs a REAL authentication test against the provider.

    Credentials are resolved exactly as a production search resolves them
    (stored row credentials first, platform `.env` values second), so a passing
    test guarantees a search will authenticate. Nothing is simulated: Mappls
    exchanges an OAuth token, Google Places and Bing issue one-result queries,
    OpenAI lists models.

    Always HTTP 200. `success=false` means the provider rejected us — see
    `details` for its status code, error body and the exception; the traceback
    is in the server log.
    """
    provider = (
        await db.execute(select(ApiProvider).where(ApiProvider.id == provider_id))
    ).scalar_one_or_none()
    if provider is None:
        raise NotFoundError("Provider not found")

    outcome = await provider_test_service.test_provider(provider)

    # Record what the probe learned: `latency_ms` powers the API Manager's
    # latency column, and a provider that just failed authentication should not
    # keep claiming to be healthy.
    if outcome.latency_ms:
        provider.latency_ms = outcome.latency_ms
    if outcome.success:
        provider.status = ProviderStatus.HEALTHY
    elif provider.status is ProviderStatus.HEALTHY:
        provider.status = ProviderStatus.DEGRADED
    await db.commit()

    return ProviderTestResult(**vars(outcome))


@router.post("/providers/system-checks", response_model=list[ProviderTestResult])
async def system_dependency_checks(
    _membership=Depends(require_permission("api_keys.manage")),
    db: AsyncSession = Depends(get_db),
    cache: Redis = Depends(get_redis),
):
    """Real checks against the infrastructure the app depends on.

    SMTP, Stripe, Redis and Postgres have no `ApiProvider` row — they are not
    lead sources — so they are tested here rather than through
    `/providers/{id}/test`. Inventing catalogue rows for them would have put
    non-provider cards in the API Manager grid.

    `smtplib` and the Stripe SDK are synchronous, so they run in a worker thread
    to keep the event loop free.
    """
    smtp, stripe_result = await asyncio.gather(
        run_in_threadpool(provider_test_service.test_smtp_sync),
        run_in_threadpool(provider_test_service.test_stripe_sync),
    )
    redis_result = await provider_test_service.test_redis(cache)
    postgres = await provider_test_service.test_postgres(db)

    return [ProviderTestResult(**vars(o)) for o in (postgres, redis_result, smtp, stripe_result)]


@router.post("/scan-website", response_model=WebsiteScanOut, status_code=201)
async def scan_website(
    payload: WebsiteScanCreate,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    exempt = usage_service.is_metering_exempt(user)
    scan = await search_service.scan_website(
        db, organization.id, user.id, payload, metering_exempt=exempt
    )
    return scan


@router.post("/scans/{scan_id}/save-lead", response_model=LeadOut, status_code=201)
async def save_scan_as_lead(
    scan_id: uuid.UUID,
    response: Response,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Saves a website scan's findings as a lead.

    Idempotent: a scan already saved returns its existing lead with 200 rather
    than creating a second one. The scan's contacts go through the same
    deduplicate -> score -> persist path as any provider result, so a company
    already in the database is linked to instead of duplicated.
    """
    scan = (
        await db.execute(
            select(WebsiteScan).where(
                WebsiteScan.id == scan_id,
                # Scoped to the org: another workspace's scan must 404, not leak.
                WebsiteScan.organization_id == organization.id,
            )
        )
    ).scalar_one_or_none()
    if scan is None:
        raise NotFoundError("Scan not found")

    lead, created = await search_service.save_scan_as_lead(db, organization.id, user.id, scan)
    if not created:
        # Nothing new was created, so 201 would be a lie.
        response.status_code = 200
    await db.refresh(lead, attribute_names=["company"])
    return LeadOut.from_lead(lead)


@router.get("/scans", response_model=Page[WebsiteScanOut])
async def list_scans(
    params: PaginationParams = Depends(pagination_params),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(WebsiteScan)
        .where(WebsiteScan.organization_id == organization.id)
        .order_by(WebsiteScan.created_at.desc())
    )
    scans, meta = await paginate(db, stmt, params)
    return Page(items=scans, meta=meta)
