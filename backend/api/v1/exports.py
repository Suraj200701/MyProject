"""Export Center endpoints: create, history, status, download, delete.

Security model
--------------
* **Tenant isolation.** Every route resolves the caller's organization via
  `get_current_organization` and every query is filtered by it. An export id from
  another organization returns 404, not 403 — a 403 would confirm the id exists.
* **RBAC.** Creating and deleting exports requires the seeded `leads.export`
  permission, which OWNER/ADMIN/MEMBER have and VIEWER does not. Reading history
  needs only organization membership, so a viewer can see that an export happened
  without being able to extract data.
* **Rate limiting.** Export *creation* carries a per-user hourly budget on top of
  the global per-IP limiter, because it is the expensive operation: one request
  can render tens of thousands of rows. Reads and downloads are cheap and stay on
  the global limiter alone.
* **Download authentication.** Two routes, one enforcement path
  (`export_service.resolve_download`): a Bearer-authenticated download for
  scripts, and a short-lived signed token for browsers, which cannot set headers
  on a plain navigation. See `utils/download_token.py`.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user, require_permission
from config.settings import settings
from database.session import get_db
from middleware.rate_limit import check_rate_limit
from models.enums import ExportFormat, ExportResource, ExportStatus
from models.organization import Organization
from models.search import Export
from models.user import User
from redis_cache.client import get_redis_pool
from schemas.common import MessageResponse
from schemas.export import DownloadTokenOut, ExportCreate, ExportOut, format_size
from services import export_datasets, export_service, exporters
from services.export_service import ExportRequest
from utils.download_token import DownloadTokenError, verify as verify_download_token
from utils.exceptions import NotFoundError, TooManyRequestsError, UnauthorizedError
from utils.pagination import Page, PaginationParams, paginate, pagination_params

router = APIRouter(prefix="/exports", tags=["Exports"])

# The permission that gates data extraction. Seeded in scripts/seed_data.py and
# granted to OWNER, ADMIN and MEMBER — not VIEWER.
EXPORT_PERMISSION = "leads.export"


def _to_export_out(export: Export, ignored_columns: list[str] | None = None) -> ExportOut:
    downloadable = export.status is ExportStatus.READY and not export_service.is_expired(export)
    return ExportOut(
        id=export.id,
        file_name=export.file_name,
        format=export.format,
        resource=export.resource,
        row_count=export.row_count,
        size_bytes=export.size_bytes,
        size_label=format_size(export.size_bytes),
        status=export.status,
        download_count=export.download_count or 0,
        created_at=export.created_at,
        expires_at=export.expires_at,
        error_message=export.error_message,
        download_url=f"/api/v1/exports/{export.id}/download" if downloadable else None,
        ignored_columns=ignored_columns or [],
    )


async def _enforce_export_budget(user_id: uuid.UUID) -> None:
    """Per-user hourly cap on export creation.

    Fails **open** if Redis is unavailable, matching the global limiter's
    behaviour: losing the cache should degrade throttling, not block a paying
    customer's exports.
    """
    redis = Redis(connection_pool=get_redis_pool())
    try:
        allowed, _remaining = await check_rate_limit(
            redis, f"export:create:{user_id}", settings.EXPORT_RATE_LIMIT_PER_HOUR, 3600
        )
    except Exception:
        return
    finally:
        await redis.aclose()

    if not allowed:
        raise TooManyRequestsError(
            f"Export limit reached ({settings.EXPORT_RATE_LIMIT_PER_HOUR} per hour). "
            f"Please wait before creating another export."
        )


@router.post(
    "",
    response_model=ExportOut,
    status_code=201,
    summary="Create an export",
    responses={
        201: {"description": "Generated inline and ready to download."},
        202: {"description": "Queued for background generation; poll GET /exports/{id}."},
        400: {"description": "Invalid request, or the selection exceeds the row/size limit."},
        403: {"description": "Your role lacks the leads.export permission."},
        429: {"description": "Per-user hourly export budget exhausted."},
    },
)
async def create_export(
    payload: ExportCreate,
    response: Response,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    _: object = Depends(require_permission(EXPORT_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Creates an export of leads, search results, or a dashboard/analytics report.

    **Sync vs background.** Selections below `EXPORT_ASYNC_ROW_THRESHOLD` rows are
    generated inline and come back `201` with `status="ready"` and a
    `download_url`. Larger lead/search exports are queued and come back `202` with
    `status="processing"` — poll `GET /exports/{id}` until it turns `ready`.
    Reports are always inline (they are small aggregates).

    **Column selection** accepts either API keys (`lead_score`) or the export
    wizard's display labels (`Lead Score`). Names that match nothing are skipped
    and listed in `ignored_columns` rather than failing the request.
    """
    await _enforce_export_budget(user.id)

    request = ExportRequest(
        resource=payload.resource,
        export_format=payload.format,
        scope=payload.scope,
        lead_ids=payload.lead_ids,
        filters=payload.filters.model_dump(exclude_none=True) if payload.filters else {},
        search_id=payload.search_id,
        columns=payload.columns,
        file_name=payload.file_name,
    )

    export = await export_service.create_export(db, organization, user.id, request)

    if export.status is ExportStatus.PROCESSING:
        response.status_code = 202

    ignored = export_datasets.unknown_column_names(export_datasets.LEAD_COLUMNS, payload.columns)
    return _to_export_out(export, ignored)


@router.get(
    "",
    response_model=Page[ExportOut],
    summary="List export history",
)
async def list_exports(
    resource: ExportResource | None = Query(default=None, description="Filter by exported resource"),
    status: ExportStatus | None = Query(default=None, description="Filter by status"),
    params: PaginationParams = Depends(pagination_params),
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated export history for the caller's organization, newest first.

    Includes failed and expired exports: an audit trail that hides failures cannot
    answer "where did my export go?", and `download_url` is null for anything not
    currently downloadable.
    """
    stmt = export_service.history_statement(organization.id, resource=resource, status=status)
    rows, meta = await paginate(db, stmt, params)
    return Page(items=[_to_export_out(row) for row in rows], meta=meta)


@router.get(
    "/formats",
    summary="List supported export formats and lead columns",
)
async def list_export_options(
    user: User = Depends(get_current_user),
):
    """Describes what this deployment can export.

    Lets the export wizard populate its format and column pickers from the server
    instead of hardcoding a list that can drift out of sync with the backend.
    """
    return {
        "formats": [
            {
                "value": fmt.value,
                "extension": exporters.extension_for(fmt),
                "media_type": exporters.media_type_for(fmt),
            }
            for fmt in ExportFormat
        ],
        "resources": [r.value for r in ExportResource],
        "scopes": ["all", "filtered", "selected"],
        "lead_columns": [
            {"key": c.key, "label": c.label} for c in export_datasets.LEAD_COLUMNS
        ],
        "default_lead_columns": list(export_datasets.DEFAULT_LEAD_COLUMN_KEYS),
        "limits": {
            "max_rows": settings.EXPORT_MAX_ROWS,
            "max_file_size_mb": settings.EXPORT_MAX_FILE_SIZE_MB,
            "async_row_threshold": settings.EXPORT_ASYNC_ROW_THRESHOLD,
            "retention_hours": settings.EXPORT_RETENTION_HOURS,
            "rate_limit_per_hour": settings.EXPORT_RATE_LIMIT_PER_HOUR,
        },
    }


@router.get(
    "/{export_id}",
    response_model=ExportOut,
    summary="Get one export's status",
)
async def get_export(
    export_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetches one export. Poll this after a `202` until `status` is `ready`."""
    export = await export_service.get_export(db, export_id, organization.id)
    return _to_export_out(export)


@router.post(
    "/{export_id}/download-token",
    response_model=DownloadTokenOut,
    summary="Mint a short-lived download token",
)
async def create_download_token(
    export_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Issues a token for downloading this export without an `Authorization` header.

    For browser downloads: `<a href>`, `window.open` and the native download
    manager all send a bare GET and cannot attach a header. Putting the access
    token in the URL instead would leak a long-lived, full-privilege credential
    into browser history and proxy logs; this token is scoped to one export, one
    user, and a few minutes.

    The download route still re-checks ownership, status and expiry — a valid
    token is not a bypass.
    """
    from utils.download_token import issue

    # Confirms the export exists, belongs to this organization, and is actually
    # downloadable before handing out a token for it.
    await export_service.resolve_download(db, export_id, organization.id)

    token, expires_in = issue(export_id, user.id)
    return DownloadTokenOut(
        token=token,
        expires_in=expires_in,
        download_url=f"/api/v1/exports/{export_id}/download?token={token}",
    )


@router.get(
    "/{export_id}/download",
    summary="Download an export file",
    response_class=FileResponse,
    responses={
        200: {"content": {"application/octet-stream": {}}, "description": "The export file."},
        400: {"description": "The export is still processing, or failed."},
        401: {"description": "No Bearer token and no valid ?token=."},
        404: {"description": "Not found in your organization, expired, or its file is gone."},
    },
)
async def download_export(
    export_id: uuid.UUID,
    request: Request,
    token: str | None = Query(
        default=None,
        description="Signed token from POST /exports/{id}/download-token. Use instead of a Bearer header for browser downloads.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Streams the export file.

    Authenticate **either** with `Authorization: Bearer <access_token>` **or** with
    a `?token=` from `POST /exports/{id}/download-token`.

    Auth is resolved manually rather than via `Depends(get_current_user)` because
    this route accepts two mutually exclusive credentials — a hard dependency on
    the bearer scheme would reject every signed-token download before the handler
    ran.
    """
    organization_id, _user_id = await _resolve_download_identity(db, request, export_id, token)

    export, path = await export_service.resolve_download(db, export_id, organization_id)
    await export_service.record_download(db, export)

    return FileResponse(
        path=path,
        media_type=exporters.media_type_for(export.format),
        filename=export.file_name,
        headers={
            "Content-Disposition": f'attachment; filename="{export.file_name}"',
            # Exports contain customer data: keep them out of shared caches, and
            # out of the browser's disk cache after the token expires.
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _resolve_download_identity(
    db: AsyncSession, request: Request, export_id: uuid.UUID, token: str | None
) -> tuple[uuid.UUID, uuid.UUID]:
    """Resolves (organization_id, user_id) from a signed token or a Bearer header."""
    if token:
        try:
            token_export_id, token_user_id = verify_download_token(token)
        except DownloadTokenError as exc:
            raise UnauthorizedError("Invalid or expired download token") from exc

        # The token names the export it is for; using it on a different id is a
        # forgery attempt, not a redirect.
        if token_export_id != export_id:
            raise UnauthorizedError("This download token is not valid for this export")

        organization_id = await _organization_for_export(db, export_id, token_user_id)
        return organization_id, token_user_id

    # Fall back to normal bearer auth. Imported here so the module-level
    # dependency graph stays free of the bearer scheme for this route.
    from api.deps import bearer_scheme, get_current_organization as resolve_org, get_current_user as resolve_user

    credentials = await bearer_scheme(request)
    if credentials is None:
        raise UnauthorizedError(
            "Provide an Authorization: Bearer header, or a ?token= from POST /exports/{id}/download-token"
        )

    user = await resolve_user(credentials=credentials, db=db)
    organization = await resolve_org(
        x_organization_id=request.headers.get("X-Organization-Id"), user=user, db=db
    )
    return organization.id, user.id


async def _organization_for_export(
    db: AsyncSession, export_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    """Finds the export's organization and confirms the token's user still belongs to it.

    Membership is re-checked at download time rather than trusted from the token:
    a user removed from the organization between minting and using a token must
    not still be able to pull the file.
    """
    from sqlalchemy import select

    from models.organization import OrganizationMember

    export = (await db.execute(select(Export).where(Export.id == export_id))).scalar_one_or_none()
    if export is None:
        raise NotFoundError("Export not found")

    membership = (
        await db.execute(
            select(OrganizationMember.id).where(
                OrganizationMember.organization_id == export.organization_id,
                OrganizationMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Export not found")

    return export.organization_id


@router.delete(
    "/{export_id}",
    response_model=MessageResponse,
    summary="Delete an export and its file",
)
async def delete_export(
    export_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    _: object = Depends(require_permission(EXPORT_PERMISSION)),
    db: AsyncSession = Depends(get_db),
):
    """Deletes an export log row and removes its stored file."""
    await export_service.delete_export(db, export_id, organization.id)
    return MessageResponse(message="Export deleted")
