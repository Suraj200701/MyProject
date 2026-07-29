"""Business logic for in-app notifications, delivery preferences, and
push subscriptions.

Runs in the main (async) FastAPI process. This is what routes call
directly for read/write of notifications — separate from
notifications/tasks.py, which is the Celery/Redis side used to fan out
emails asynchronously.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import NotificationType
from models.notification import Notification, NotificationPreference, PushSubscription
from models.user import User
from schemas.notification import NotificationPreferenceUpdate, PushSubscriptionCreate
from utils.exceptions import NotFoundError
from utils.pagination import Page, PaginationParams, paginate


async def list_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    params: PaginationParams,
    unread_only: bool = False,
) -> Page:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc())

    items, meta = await paginate(db, stmt, params)
    return Page(items=items, meta=meta)


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    return (await db.execute(stmt)).scalar_one()


async def mark_read(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification:
    stmt = select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
    notification = (await db.execute(stmt)).scalar_one_or_none()
    if notification is None:
        raise NotFoundError("Notification not found")

    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(notification)

    return notification


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


async def notify(
    db: AsyncSession,
    user_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    type_: NotificationType,
    title: str,
    description: str | None = None,
    extra_data: dict | None = None,
) -> Notification:
    """Creates the Notification row directly (synchronously, in-request,
    via the async session — simpler and avoids needing Celery on the hot
    path for in-app notifications), then fans out an email asynchronously
    via Celery/Redis if the user's preference for this category allows
    it (default: enabled, if no preference row exists yet)."""
    notification = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        organization_id=organization_id,
        type=type_,
        title=title,
        description=description,
        extra_data=extra_data,
        created_at=datetime.now(UTC),
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    pref_stmt = select(NotificationPreference).where(
        NotificationPreference.user_id == user_id, NotificationPreference.category == type_
    )
    preference = (await db.execute(pref_stmt)).scalar_one_or_none()
    email_enabled = preference.email_enabled if preference is not None else True

    if email_enabled:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is not None:
            from notifications.tasks import send_notification_email_task

            send_notification_email_task.delay(user.email, title, description or title)

    return notification


async def get_preferences(db: AsyncSession, user_id: uuid.UUID) -> list[NotificationPreference]:
    stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    existing = (await db.execute(stmt)).scalars().all()
    existing_categories = {p.category for p in existing}

    missing = [c for c in NotificationType if c not in existing_categories]
    created: list[NotificationPreference] = []
    for category in missing:
        preference = NotificationPreference(
            id=uuid.uuid4(),
            user_id=user_id,
            category=category,
            email_enabled=True,
            push_enabled=True,
            in_app_enabled=True,
        )
        db.add(preference)
        created.append(preference)

    if created:
        await db.commit()
        for preference in created:
            await db.refresh(preference)

    return list(existing) + created


async def update_preference(
    db: AsyncSession,
    user_id: uuid.UUID,
    category: NotificationType,
    updates: NotificationPreferenceUpdate,
) -> NotificationPreference:
    stmt = select(NotificationPreference).where(
        NotificationPreference.user_id == user_id, NotificationPreference.category == category
    )
    preference = (await db.execute(stmt)).scalar_one_or_none()

    if preference is None:
        preference = NotificationPreference(
            id=uuid.uuid4(),
            user_id=user_id,
            category=category,
            email_enabled=True,
            push_enabled=True,
            in_app_enabled=True,
        )
        db.add(preference)

    data = updates.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(preference, field, value)

    await db.commit()
    await db.refresh(preference)
    return preference


async def register_push_subscription(
    db: AsyncSession, user_id: uuid.UUID, data: PushSubscriptionCreate
) -> PushSubscription:
    stmt = select(PushSubscription).where(PushSubscription.endpoint == data.endpoint)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        existing.user_id = user_id
        existing.p256dh_key = data.p256dh_key
        existing.auth_key = data.auth_key
        await db.commit()
        await db.refresh(existing)
        return existing

    subscription = PushSubscription(
        id=uuid.uuid4(),
        user_id=user_id,
        endpoint=data.endpoint,
        p256dh_key=data.p256dh_key,
        auth_key=data.auth_key,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription
