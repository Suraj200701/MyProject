"""Synchronous SQLAlchemy engine + session factory.

The rest of the app (database/session.py) is async, but Celery's default
worker pool is not async-native — fighting that inside every task isn't
worth it. This module gives Celery tasks a small, plain synchronous
engine/session against the same Postgres database instead.

Use this ONLY from within Celery tasks (notifications/tasks.py). FastAPI
routes and services should keep using database/session.py's async
engine/session.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings

sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """Context-managed sync session for use inside Celery task bodies."""
    session = SyncSessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
