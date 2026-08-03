"""Celery tasks for the Export Center: large-export generation and cleanup.

Runs in the sync worker, following the pattern already established by
`notifications/tasks.py` — a plain synchronous session from
`database/sync_session.py` rather than trying to drive the app's async engine
from Celery's non-async pool. Reusing that async engine across a worker's
per-task event loops is exactly the "attached to a different loop" failure it
looks like, so it is avoided entirely.

No query is duplicated to achieve that: `services/export_datasets.py` exposes its
queries as plain SQLAlchemy `Select` objects plus pure row mappers, which are
valid on either engine. Only the `execute` call differs.

Two tasks:

* `exports.generate_export` — builds one queued export. Reconstructs the request
  from the JSON stored on `Export.filters`, so the worker needs nothing from the
  originating HTTP request.
* `exports.purge_expired_exports` — deletes files past their retention window.
  Scheduled hourly by Celery beat (see `notifications/celery_app.py`). This is
  the temporary-file cleanup mechanism; it is idempotent, so a missed run simply
  catches up on the next tick.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from config.settings import settings
from models.enums import ExportResource, ExportStatus
from notifications.celery_app import celery_app

logger = logging.getLogger("leadmaster.exports.tasks")


@celery_app.task(name="exports.generate_export", bind=True, max_retries=2, default_retry_delay=30)
def generate_export_task(self, export_id: str) -> dict:
    """Generates a queued export and flips its row to READY (or FAILED).

    Imports are function-local so importing this module (which
    `export_service` does when enqueueing) cannot drag the sync engine and the
    ORM into the web process at import time.
    """
    from database.sync_session import get_sync_db
    from models.organization import Organization
    from models.search import Export, Search
    from services import export_datasets, exporters, storage
    from services.export_service import ExportRequest

    with get_sync_db() as db:
        export = db.get(Export, uuid.UUID(export_id))
        if export is None:
            logger.error("Export %s no longer exists; nothing to generate", export_id)
            return {"export_id": export_id, "status": "missing"}

        if export.status is not ExportStatus.PROCESSING:
            # Already handled. Makes the task idempotent under Celery's
            # at-least-once delivery, so a redelivered message cannot produce a
            # second file for the same row.
            logger.info("Export %s is %s, not processing; skipping", export_id, export.status.value)
            return {"export_id": export_id, "status": export.status.value}

        try:
            request = ExportRequest.from_json(export.filters or {})
            organization = db.get(Organization, export.organization_id)
            if organization is None:
                raise RuntimeError("Organization no longer exists")

            columns = export_datasets.resolve_columns(export_datasets.LEAD_COLUMNS, request.columns)
            max_rows = settings.EXPORT_MAX_ROWS

            if request.resource is ExportResource.SEARCH_RESULTS:
                search = db.get(Search, request.search_id) if request.search_id else None
                if search is None or search.organization_id != export.organization_id:
                    raise RuntimeError("Search no longer exists")
                dataset = export_datasets.load_search_results_dataset_sync(
                    db,
                    organization_id=organization.id,
                    organization_name=organization.name,
                    search=search,
                    columns=columns,
                    max_rows=max_rows,
                )
            elif request.resource is ExportResource.LEADS:
                dataset = export_datasets.load_leads_dataset_sync(
                    db,
                    organization_id=organization.id,
                    organization_name=organization.name,
                    columns=columns,
                    scope_label=request.scope_label,
                    lead_ids=request.lead_ids if request.scope == "selected" else None,
                    filters=request.filters,
                    max_rows=max_rows,
                )
            else:
                # Reports are always generated inline (they are async-only
                # aggregates and never large enough to queue), so reaching here
                # means a queued row was created for a resource that cannot be
                # built here. Fail loudly rather than leaving it PROCESSING.
                raise RuntimeError(
                    f"Resource {request.resource.value} cannot be generated in the background"
                )

            blob = exporters.render(dataset, request.format)

            size_limit = settings.EXPORT_MAX_FILE_SIZE_MB * 1024 * 1024
            if len(blob) > size_limit:
                raise RuntimeError(
                    f"Generated file is {len(blob) / 1024 / 1024:.1f}MB, above the "
                    f"{settings.EXPORT_MAX_FILE_SIZE_MB}MB limit"
                )

            key = storage.generate_storage_key(organization.id, export.file_name, "exports")
            path = Path(settings.UPLOAD_DIR) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)

            export.storage_path = str(path)
            export.row_count = dataset.row_count
            export.size_bytes = len(blob)
            export.status = ExportStatus.READY
            export.error_message = None
            export.expires_at = datetime.now(UTC) + timedelta(hours=settings.EXPORT_RETENTION_HOURS)
            db.commit()

            logger.info(
                "Export %s generated (%s rows, %s bytes)", export_id, export.row_count, export.size_bytes
            )
            return {"export_id": export_id, "status": "ready", "rows": export.row_count}

        except Exception as exc:  # noqa: BLE001 - must always land the row somewhere
            db.rollback()
            logger.exception("Background export %s failed", export_id)

            # Retry transient problems; on the final attempt record FAILED so the
            # row never sits at PROCESSING forever.
            if self.request.retries < self.max_retries:
                export = db.get(Export, uuid.UUID(export_id))
                if export is not None:
                    export.error_message = f"Attempt {self.request.retries + 1} failed: {type(exc).__name__}"[:500]
                    db.commit()
                raise self.retry(exc=exc)

            export = db.get(Export, uuid.UUID(export_id))
            if export is not None:
                export.status = ExportStatus.FAILED
                export.error_message = f"{type(exc).__name__}: {exc}"[:500]
                db.commit()
            return {"export_id": export_id, "status": "failed", "error": str(exc)[:200]}


@celery_app.task(name="exports.purge_expired_exports")
def purge_expired_exports_task() -> dict:
    """Deletes files for exports past their retention window.

    Rows are kept and marked EXPIRED — the audit trail of who extracted what is
    worth more than the bytes, `GET /dashboard/export-analytics` keeps working
    over historical months, and the download endpoint can answer "expired"
    instead of "not found".
    """
    from database.sync_session import get_sync_db
    from models.search import Export
    from sqlalchemy import select

    now = datetime.now(UTC)
    files_deleted = 0

    with get_sync_db() as db:
        stale = (
            db.execute(
                select(Export).where(
                    Export.expires_at.is_not(None),
                    Export.expires_at < now,
                    Export.status != ExportStatus.EXPIRED,
                )
            )
            .scalars()
            .all()
        )

        for export in stale:
            if export.storage_path:
                try:
                    Path(export.storage_path).unlink(missing_ok=True)
                    files_deleted += 1
                except OSError as exc:
                    # Keep going: one undeletable file must not block the sweep.
                    logger.warning("Could not delete %s: %s", export.storage_path, exc)
            export.status = ExportStatus.EXPIRED
            export.storage_path = None

        if stale:
            db.commit()

    if stale:
        logger.info("Purge marked %s export(s) expired, deleted %s file(s)", len(stale), files_deleted)
    return {"expired": len(stale), "files_deleted": files_deleted}


@celery_app.task(name="exports.sweep_orphaned_export_files")
def sweep_orphaned_export_files_task() -> dict:
    """Removes export files on disk that no `Export` row references.

    Belt-and-braces for the cases the row-driven purge cannot see: a worker that
    wrote its file and died before committing, or a row deleted by a cascade when
    its organization was removed. Only touches the `exports/` segment of the
    upload directory, and only files older than the retention window, so it can
    never race a download of a fresh file.
    """
    from database.sync_session import get_sync_db
    from models.search import Export
    from sqlalchemy import select

    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.exists():
        return {"scanned": 0, "deleted": 0}

    cutoff = datetime.now(UTC) - timedelta(hours=settings.EXPORT_RETENTION_HOURS)

    with get_sync_db() as db:
        known = {
            row[0]
            for row in db.execute(select(Export.storage_path).where(Export.storage_path.is_not(None))).all()
            if row[0]
        }

    scanned = 0
    deleted = 0
    # Local storage lays files out as {org_id}/exports/{uuid}_{name}.
    for path in upload_root.glob("*/exports/*"):
        if not path.is_file():
            continue
        scanned += 1
        if str(path) in known:
            continue
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if modified > cutoff:
                continue  # too new to be sure it is orphaned
            path.unlink(missing_ok=True)
            deleted += 1
        except OSError as exc:
            logger.warning("Could not sweep %s: %s", path, exc)

    if deleted:
        logger.info("Swept %s orphaned export file(s) of %s scanned", deleted, scanned)
    return {"scanned": scanned, "deleted": deleted}
