"""Celery application for LeadMaster AI's asynchronous notification
fan-out (emails, push, etc.), backed by Redis as both broker and result
backend.

Run the worker (see docker-compose.yml) with:
    celery -A notifications.celery_app worker
"""

from celery import Celery

from config.settings import settings

celery_app = Celery(
    "leadmaster",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["notifications.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)
