"""Celery application for LeadMaster AI's asynchronous work, backed by Redis as
both broker and result backend.

Two task modules are registered:
  * `notifications.tasks`   — notification fan-out (emails, push)
  * `services.export_tasks` — Export Center: large-export generation and the
                              expired-file cleanup sweep

Run the worker (see docker-compose.yml) with:
    celery -A notifications.celery_app worker

The cleanup tasks are periodic, so a beat scheduler is also required:
    celery -A notifications.celery_app beat

Beat must run as a SINGLE instance (multiple beats means duplicated ticks); the
worker scales horizontally.
"""

from celery import Celery
from celery.schedules import crontab

from config.settings import settings

celery_app = Celery(
    "leadmaster",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["notifications.tasks", "services.export_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    # Export retention. Hourly is fine at any EXPORT_RETENTION_HOURS setting:
    # files live at most an hour past their expiry, and the task is idempotent so
    # a missed tick catches up on the next one.
    "purge-expired-exports": {
        "task": "exports.purge_expired_exports",
        "schedule": crontab(minute=5),
    },
    # Catches files the row-driven purge cannot see (a worker that wrote its file
    # then died before committing, or rows removed by an organization cascade).
    # Daily and off-peak: it walks the upload directory, and it only removes
    # files already older than the retention window.
    "sweep-orphaned-export-files": {
        "task": "exports.sweep_orphaned_export_files",
        "schedule": crontab(hour=3, minute=20),
    },
}
