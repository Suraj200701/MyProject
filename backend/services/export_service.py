"""Export Center orchestration.

Responsibilities, in the order a request hits them:

    validate the request  ->  count the rows it would produce  ->  enforce the
    row cap  ->  decide inline vs background  ->  build the dataset  ->  render
    bytes  ->  enforce the size cap  ->  persist to storage  ->  write the
    `Export` log row

Where the pieces live: `export_datasets.py` decides *what* is in an export,
`services/exporters/` decides what the bytes look like, and this module decides
*when and how* an export is produced and who may read it back.

Guarantees this module is responsible for
-----------------------------------------
* **Tenant isolation.** Every query is filtered by `organization_id`, including
  on the download and delete paths. An export id from another organization is a
  404, not a 403 — a 403 would confirm the id exists.
* **Row cap** (`EXPORT_MAX_ROWS`) is checked *before* generating, so an oversized
  request costs a COUNT rather than a render. When a scope legitimately exceeds
  it, the export is capped and says so in the file's own metadata rather than
  silently returning partial data.
* **Size cap** (`EXPORT_MAX_FILE_SIZE_MB`) is checked *after* rendering, because
  the only honest way to know a PDF's size is to build it. The file is discarded
  and the row marked FAILED rather than stored.
* **Expiry.** Exports are disposable artifacts. Every row gets `expires_at`, the
  download path refuses anything past it, and `purge_expired_exports` deletes the
  bytes.

Failure policy: a failed export still writes an `Export` row with status FAILED
and an `error_message`. The attempt is part of the audit trail — and a history
list that silently omits failures is how "my export never appeared" becomes
unanswerable.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.enums import ExportFormat, ExportResource, ExportStatus
from models.organization import Organization
from models.search import Export, Search, WebsiteScan
from services import export_datasets, exporters, storage
from services.exporters.dataset import Dataset
from utils.exceptions import BadRequestError, NotFoundError

logger = logging.getLogger("leadmaster.exports")

# Storage key segment, so export files are grouped under the organization's
# prefix and never collide with uploaded documents.
_STORAGE_SEGMENT = "exports"


class ExportTooLargeError(BadRequestError):
    """413-ish condition surfaced as 400 with an actionable message.

    Deliberately a 400 rather than 413: 413 is about the *request* body, and here
    it is the response the caller asked us to build that is too large.
    """

    def __init__(self, detail: str):
        super().__init__(detail)


# --- Request description --------------------------------------------------


class ExportRequest:
    """Normalized, already-validated description of what to export.

    A small class rather than passing the Pydantic schema around, so the Celery
    worker can rebuild one from the JSON persisted on `Export.filters` without
    importing the API schema layer.
    """

    def __init__(
        self,
        *,
        resource: ExportResource,
        export_format: ExportFormat,
        scope: str = "all",
        lead_ids: list[uuid.UUID] | None = None,
        filters: dict | None = None,
        search_id: uuid.UUID | None = None,
        scan_id: uuid.UUID | None = None,
        columns: list[str] | None = None,
        file_name: str | None = None,
    ) -> None:
        self.resource = resource
        self.format = export_format
        self.scope = scope
        self.lead_ids = lead_ids or []
        self.filters = filters or {}
        self.search_id = search_id
        self.scan_id = scan_id
        self.columns = columns or []
        self.file_name = file_name

    @property
    def scope_label(self) -> str:
        if self.scope == "selected":
            return f"{len(self.lead_ids)} selected lead(s)"
        if self.scope == "filtered":
            described = export_datasets._describe_filters(self.filters)
            return f"Filtered view ({described})" if described else "Filtered view"
        return "All leads"

    def to_json(self) -> dict:
        """Serializable form, stored on `Export.filters`.

        This is what lets a background job reconstruct the exact selection after
        the originating request has ended, and what the history list renders to
        show *what* an export contained.
        """
        return {
            "resource": self.resource.value,
            "format": self.format.value,
            "scope": self.scope,
            "lead_ids": [str(i) for i in self.lead_ids],
            "filters": _json_safe_filters(self.filters),
            "search_id": str(self.search_id) if self.search_id else None,
            "scan_id": str(self.scan_id) if self.scan_id else None,
            "columns": list(self.columns),
            "file_name": self.file_name,
        }

    @classmethod
    def from_json(cls, payload: dict) -> "ExportRequest":
        return cls(
            resource=ExportResource(payload["resource"]),
            export_format=ExportFormat(payload["format"]),
            scope=payload.get("scope") or "all",
            lead_ids=[uuid.UUID(i) for i in (payload.get("lead_ids") or [])],
            filters=payload.get("filters") or {},
            search_id=uuid.UUID(payload["search_id"]) if payload.get("search_id") else None,
            scan_id=uuid.UUID(payload["scan_id"]) if payload.get("scan_id") else None,
            columns=payload.get("columns") or [],
            file_name=payload.get("file_name"),
        )


def _json_safe_filters(filters: dict) -> dict:
    """Coerces filter values to JSON-serializable primitives.

    `filters` reaches JSONB, and a stray UUID (e.g. `search_id`) would raise at
    flush time rather than at the boundary.
    """
    safe: dict = {}
    for key, value in (filters or {}).items():
        if value is None:
            continue
        safe[key] = str(value) if isinstance(value, uuid.UUID) else value
    return safe


# --- Validation -----------------------------------------------------------


async def validate_request(db: AsyncSession, organization_id: uuid.UUID, request: ExportRequest) -> Search | None:
    """Checks resource-specific preconditions. Returns the resolved Search, if any."""
    if request.resource is ExportResource.SEARCH_RESULTS:
        if request.search_id is None:
            raise BadRequestError(
                "search_id is required when resource is 'search_results' — it identifies "
                "which search's results to export."
            )
        search = (
            await db.execute(
                select(Search).where(
                    Search.id == request.search_id,
                    # Org-scoped: another organization's search id must not be
                    # exportable, and must not be distinguishable from a
                    # nonexistent one.
                    Search.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if search is None:
            raise NotFoundError("Search not found")
        return search

    if request.resource is ExportResource.WEBSITE_SCANS and request.scan_id is not None:
        # scan_id is optional (omit it to export every scan), but a supplied one
        # must exist in this organization — another org's id has to 404, not leak.
        scan = (
            await db.execute(
                select(WebsiteScan).where(
                    WebsiteScan.id == request.scan_id,
                    WebsiteScan.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if scan is None:
            raise NotFoundError("Scan not found")
        return None

    if request.scope == "selected" and not request.lead_ids:
        raise BadRequestError("lead_ids must not be empty when scope is 'selected'")

    return None


# --- Row counting (preflight) --------------------------------------------


async def estimate_row_count(
    db: AsyncSession, organization_id: uuid.UUID, request: ExportRequest
) -> int:
    """How many rows this request would produce, without building anything.

    Reports return 0 — they are aggregates whose size is bounded by the number of
    metrics, not by the lead table, so a COUNT is meaningless and they never
    approach the row cap.
    """
    if request.resource in (ExportResource.DASHBOARD_REPORT, ExportResource.ANALYTICS_REPORT):
        return 0

    if request.resource is ExportResource.WEBSITE_SCANS:
        stmt = export_datasets.scans_statement(organization_id, request.scan_id)
        return (await db.execute(export_datasets.count_statement(stmt))).scalar_one()

    filters = dict(request.filters)
    if request.resource is ExportResource.SEARCH_RESULTS:
        filters = {"search_id": request.search_id}

    stmt = export_datasets.leads_statement(
        organization_id,
        lead_ids=request.lead_ids if request.scope == "selected" else None,
        filters=filters,
    )
    return (await db.execute(export_datasets.count_statement(stmt))).scalar_one()


def should_run_in_background(row_count: int, resource: ExportResource) -> bool:
    """Whether this export is handed to Celery instead of generated inline."""
    if not export_datasets.supports_background(resource):
        return False
    return row_count >= settings.EXPORT_ASYNC_ROW_THRESHOLD


# --- Dataset building ----------------------------------------------------


async def build_dataset(
    db: AsyncSession,
    organization: Organization,
    request: ExportRequest,
    search: Search | None = None,
) -> Dataset:
    """Builds the `Dataset` for a request on the async (request) path."""
    columns = export_datasets.resolve_columns(
        export_datasets.columns_for(request.resource), request.columns
    )
    max_rows = settings.EXPORT_MAX_ROWS

    if request.resource is ExportResource.LEADS:
        return await export_datasets.load_leads_dataset(
            db,
            organization_id=organization.id,
            organization_name=organization.name,
            columns=columns,
            scope_label=request.scope_label,
            lead_ids=request.lead_ids if request.scope == "selected" else None,
            filters=request.filters,
            max_rows=max_rows,
        )

    if request.resource is ExportResource.SEARCH_RESULTS:
        if search is None:
            raise BadRequestError("Search could not be resolved for this export")
        return await export_datasets.load_search_results_dataset(
            db,
            organization_id=organization.id,
            organization_name=organization.name,
            search=search,
            columns=columns,
            max_rows=max_rows,
        )

    if request.resource is ExportResource.WEBSITE_SCANS:
        return await export_datasets.load_scans_dataset(
            db,
            organization_id=organization.id,
            organization_name=organization.name,
            columns=columns,
            max_rows=max_rows,
            scan_id=request.scan_id,
        )

    if request.resource is ExportResource.DASHBOARD_REPORT:
        return await export_datasets.load_dashboard_dataset(
            db, organization_id=organization.id, organization_name=organization.name
        )

    if request.resource is ExportResource.ANALYTICS_REPORT:
        return await export_datasets.load_analytics_dataset(
            db, organization_id=organization.id, organization_name=organization.name
        )

    raise BadRequestError(f"Unsupported export resource: {request.resource}")


# --- Rendering + persistence ---------------------------------------------


def _default_stem(resource: ExportResource) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{resource.value}_{stamp}"


def check_size(blob: bytes, file_name: str) -> None:
    """Enforces the generated-file size cap."""
    limit = settings.EXPORT_MAX_FILE_SIZE_MB * 1024 * 1024
    if len(blob) > limit:
        raise ExportTooLargeError(
            f"The generated export is {len(blob) / 1024 / 1024:.1f}MB, above the "
            f"{settings.EXPORT_MAX_FILE_SIZE_MB}MB limit. Narrow the filters, choose "
            f"fewer columns, or export as CSV (the most compact format)."
        )


async def render_and_store(
    dataset: Dataset, request: ExportRequest, organization_id: uuid.UUID
) -> tuple[str, str, bytes]:
    """Renders the dataset and writes it to storage.

    Returns `(file_name, storage_path, blob)`.
    """
    stem = request.file_name or _default_stem(request.resource)
    file_name = exporters.build_file_name(stem, request.format)

    blob = exporters.render(dataset, request.format)
    check_size(blob, file_name)

    backend = storage.get_storage_backend()
    key = storage.generate_storage_key(organization_id, file_name, _STORAGE_SEGMENT)
    storage_path = await backend.save(blob, key)
    return file_name, storage_path, blob


def expiry_from_now() -> datetime:
    return datetime.now(UTC) + timedelta(hours=settings.EXPORT_RETENTION_HOURS)


async def create_export(
    db: AsyncSession,
    organization: Organization,
    user_id: uuid.UUID,
    request: ExportRequest,
) -> Export:
    """Creates an export, inline or queued depending on its size.

    Always returns a persisted `Export`. Its `status` tells the caller what
    happened: READY (file available now), PROCESSING (queued — poll
    `GET /exports/{id}`), or FAILED (with `error_message`).
    """
    search = await validate_request(db, organization.id, request)
    row_count = await estimate_row_count(db, organization.id, request)

    if row_count > settings.EXPORT_MAX_ROWS:
        raise ExportTooLargeError(
            f"This selection matches {row_count:,} rows, above the per-export limit of "
            f"{settings.EXPORT_MAX_ROWS:,}. Narrow the filters or export in batches."
        )

    if should_run_in_background(row_count, request.resource):
        return await _queue_export(db, organization, user_id, request, row_count)

    return await _generate_inline(db, organization, user_id, request, search)


async def _generate_inline(
    db: AsyncSession,
    organization: Organization,
    user_id: uuid.UUID,
    request: ExportRequest,
    search: Search | None,
) -> Export:
    try:
        dataset = await build_dataset(db, organization, request, search)
        file_name, storage_path, blob = await render_and_store(dataset, request, organization.id)
    except ExportTooLargeError as exc:
        # Recorded as a failed attempt so it shows in history with a reason,
        # then re-raised so the caller gets the actionable 400.
        await _record_failure(db, organization.id, user_id, request, str(exc.detail))
        raise
    except Exception as exc:  # noqa: BLE001 - every failure must be logged and recorded
        logger.exception("Export generation failed for org %s", organization.id)
        await _record_failure(
            db, organization.id, user_id, request, f"{type(exc).__name__}: {exc}"[:500]
        )
        raise

    export = Export(
        organization_id=organization.id,
        user_id=user_id,
        file_name=file_name,
        format=request.format,
        resource=request.resource,
        row_count=dataset.row_count,
        size_bytes=len(blob),
        status=ExportStatus.READY,
        storage_path=storage_path,
        expires_at=expiry_from_now(),
        filters=request.to_json(),
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)
    logger.info(
        "Export %s ready for org %s (%s, %s rows, %s bytes)",
        export.id, organization.id, request.format.value, export.row_count, export.size_bytes,
    )
    return export


async def _queue_export(
    db: AsyncSession,
    organization: Organization,
    user_id: uuid.UUID,
    request: ExportRequest,
    row_count: int,
) -> Export:
    """Persists a PROCESSING row and hands generation to Celery."""
    stem = request.file_name or _default_stem(request.resource)
    export = Export(
        organization_id=organization.id,
        user_id=user_id,
        file_name=exporters.build_file_name(stem, request.format),
        format=request.format,
        resource=request.resource,
        # The preflight count, so the client can show progress against a target
        # before the file exists. Overwritten with the real figure on completion.
        row_count=row_count,
        size_bytes=0,
        status=ExportStatus.PROCESSING,
        storage_path=None,
        expires_at=expiry_from_now(),
        filters=request.to_json(),
    )
    db.add(export)
    # Committed before enqueueing: the worker looks the row up by id, so it must
    # be visible to another connection before the task can run.
    await db.commit()
    await db.refresh(export)

    try:
        from services.export_tasks import generate_export_task

        generate_export_task.delay(str(export.id))
    except Exception as exc:  # noqa: BLE001 - broker down must not lose the row
        # The row stays PROCESSING and the reason is recorded. Marking it FAILED
        # here would be wrong if the broker is merely unreachable for a moment
        # and the task is later retried by an operator.
        logger.error("Could not enqueue export %s: %s", export.id, exc)
        export.error_message = f"Queued but not dispatched: {type(exc).__name__}. Retry or run the worker."
        await db.commit()
        await db.refresh(export)

    logger.info("Export %s queued for org %s (%s rows)", export.id, organization.id, row_count)
    return export


async def _record_failure(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    request: ExportRequest,
    message: str,
) -> Export:
    # The in-flight transaction may be poisoned by whatever just failed, so start
    # clean before writing the audit row.
    await db.rollback()
    stem = request.file_name or _default_stem(request.resource)
    export = Export(
        organization_id=organization_id,
        user_id=user_id,
        file_name=exporters.build_file_name(stem, request.format),
        format=request.format,
        resource=request.resource,
        row_count=0,
        size_bytes=0,
        status=ExportStatus.FAILED,
        error_message=message[:500],
        filters=request.to_json(),
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)
    return export


# --- Reads ---------------------------------------------------------------


def history_statement(organization_id: uuid.UUID, *, resource: ExportResource | None = None,
                      status: ExportStatus | None = None):
    """Export history for one organization, newest first."""
    stmt = select(Export).where(Export.organization_id == organization_id)
    if resource is not None:
        stmt = stmt.where(Export.resource == resource)
    if status is not None:
        stmt = stmt.where(Export.status == status)
    return stmt.order_by(Export.created_at.desc(), Export.id.desc())


async def get_export(db: AsyncSession, export_id: uuid.UUID, organization_id: uuid.UUID) -> Export:
    """Fetches one export, scoped to the organization.

    A row belonging to another organization raises 404 rather than 403: a 403
    would confirm that the id exists, which is itself information.
    """
    export = (
        await db.execute(
            select(Export).where(Export.id == export_id, Export.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if export is None:
        raise NotFoundError("Export not found")
    return export


def is_expired(export: Export) -> bool:
    if export.expires_at is None:
        return False
    expires_at = export.expires_at
    if expires_at.tzinfo is None:
        # Defensive: the column is timezone-aware, but a driver or a fixture can
        # hand back a naive value, and comparing naive to aware raises.
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at < datetime.now(UTC)


async def resolve_download(
    db: AsyncSession, export_id: uuid.UUID, organization_id: uuid.UUID
) -> tuple[Export, Path]:
    """Validates an export is downloadable and returns it with its file path.

    Checked here rather than in the route so the Bearer and signed-token download
    paths cannot drift apart on what they enforce.
    """
    export = await get_export(db, export_id, organization_id)

    if export.status is ExportStatus.PROCESSING:
        raise BadRequestError(
            "This export is still being generated. Poll GET /exports/{id} until its "
            "status is 'ready'."
        )
    if export.status is ExportStatus.FAILED:
        raise BadRequestError(f"This export failed and has no file: {export.error_message or 'unknown error'}")
    if export.status is ExportStatus.EXPIRED or is_expired(export):
        raise NotFoundError(
            f"This export expired after {settings.EXPORT_RETENTION_HOURS}h and its file "
            f"has been deleted. Create a new export."
        )
    if not export.storage_path:
        raise NotFoundError("This export has no stored file")

    path = Path(export.storage_path)
    if not path.exists():
        raise NotFoundError("Export file content not found in storage")

    return export, path


async def record_download(db: AsyncSession, export: Export) -> None:
    """Bumps the download audit counter."""
    export.download_count = (export.download_count or 0) + 1
    await db.commit()


async def delete_export(db: AsyncSession, export_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    """Deletes an export row and its stored bytes."""
    export = await get_export(db, export_id, organization_id)
    await _delete_file(export)
    await db.delete(export)
    await db.commit()


async def _delete_file(export: Export) -> None:
    """Removes an export's bytes. Never raises — the row must still be cleanable."""
    if not export.storage_path:
        return
    try:
        backend = storage.get_storage_backend()
        # `storage_path` is the absolute path returned by save(); the local
        # backend's delete() takes a key relative to its base dir, so unlink
        # directly rather than round-tripping a path back into a key.
        if isinstance(backend, storage.LocalStorageBackend):
            Path(export.storage_path).unlink(missing_ok=True)
        else:  # pragma: no cover - only reachable once a remote backend exists
            await backend.delete(export.storage_path)
    except OSError as exc:
        logger.warning("Could not delete export file %s: %s", export.storage_path, exc)


# --- Cleanup -------------------------------------------------------------


async def purge_expired_exports(db: AsyncSession, *, now: datetime | None = None) -> dict[str, int]:
    """Deletes the files of exports past their retention window.

    The `Export` rows are kept and marked EXPIRED rather than deleted, for three
    reasons: history stays honest about what was exported (an audit trail of who
    extracted what data is worth more than the bytes), `GET /dashboard/export-analytics`
    keeps working over historical months, and the download endpoint can say
    "expired" instead of "not found".

    Idempotent, so it is safe on a schedule and safe to run manually.
    """
    moment = now or datetime.now(UTC)
    stmt = select(Export).where(
        Export.expires_at.is_not(None),
        Export.expires_at < moment,
        Export.status != ExportStatus.EXPIRED,
    )
    stale = (await db.execute(stmt)).scalars().all()

    files_deleted = 0
    for export in stale:
        if export.storage_path:
            await _delete_file(export)
            files_deleted += 1
        export.status = ExportStatus.EXPIRED
        export.storage_path = None

    if stale:
        await db.commit()
        logger.info("Purged %s expired export(s), deleted %s file(s)", len(stale), files_deleted)

    return {"expired": len(stale), "files_deleted": files_deleted}
