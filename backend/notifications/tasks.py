"""Celery tasks for LeadMaster AI notifications.

These run in a separate sync worker process (`celery -A
notifications.celery_app worker`) — kept deliberately simple/synchronous
rather than fighting Celery's default (non-async) worker pool. Services
running in the main FastAPI process enqueue work here via `.delay(...)`
instead of blocking the request.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from notifications.celery_app import celery_app
from notifications.email_service import send_email

logger = logging.getLogger("leadmaster.notifications.tasks")


@celery_app.task(name="notifications.send_notification_email_task")
def send_notification_email_task(user_email: str, subject: str, html_body: str) -> None:
    """Sends a single notification email via the existing (async) SMTP
    email service. Each Celery task invocation gets its own fresh event
    loop, so `asyncio.run` is safe here."""
    asyncio.run(send_email(user_email, subject, html_body))


@celery_app.task(name="notifications.create_notification_task")
def create_notification_task(
    user_id: str,
    organization_id: str | None,
    type_: str,
    title: str,
    description: str,
    extra_data: dict | None = None,
) -> str:
    """Inserts a Notification row via a plain sync session. This is the
    core "fan-out" primitive other services call asynchronously
    (`.delay(...)`) instead of blocking the request."""
    # Imported lazily so this module (and celery_app) stays importable
    # even before models are fully wired for the sync engine's metadata.
    from database.sync_session import get_sync_db
    from models.notification import Notification

    with get_sync_db() as db:
        notification = Notification(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            organization_id=uuid.UUID(organization_id) if organization_id else None,
            type=type_,
            title=title,
            description=description,
            extra_data=extra_data,
            created_at=datetime.now(UTC),
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return str(notification.id)
