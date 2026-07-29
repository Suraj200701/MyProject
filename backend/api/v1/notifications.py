"""Notification endpoints: list/read in-app notifications, delivery
preferences, and web-push subscription registration."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from database.session import get_db
from models.enums import NotificationType
from models.user import User
from schemas.common import DataResponse, MessageResponse
from schemas.notification import (
    NotificationOut,
    NotificationPreferenceOut,
    NotificationPreferenceUpdate,
    PushSubscriptionCreate,
)
from services import notification_service
from utils.exceptions import BadRequestError
from utils.pagination import Page, PaginationParams, pagination_params

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=Page[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(default=False),
    params: PaginationParams = Depends(pagination_params),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.list_notifications(db, user.id, params, unread_only=unread_only)


@router.get("/unread-count", response_model=DataResponse[int])
async def unread_count(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = await notification_service.get_unread_count(db, user.id)
    return DataResponse(data=count)


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.mark_read(db, notification_id, user.id)


@router.post("/read-all", response_model=MessageResponse)
async def mark_all_read(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    count = await notification_service.mark_all_read(db, user.id)
    return MessageResponse(message=f"Marked {count} notification(s) as read")


@router.get("/preferences", response_model=list[NotificationPreferenceOut])
async def get_preferences(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await notification_service.get_preferences(db, user.id)


@router.patch("/preferences/{category}", response_model=NotificationPreferenceOut)
async def update_preference(
    category: str,
    payload: NotificationPreferenceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        category_enum = NotificationType(category)
    except ValueError as exc:
        valid = ", ".join(c.value for c in NotificationType)
        raise BadRequestError(f"Invalid category '{category}'. Must be one of: {valid}") from exc

    return await notification_service.update_preference(db, user.id, category_enum, payload)


@router.post("/push-subscriptions", response_model=MessageResponse, status_code=201)
async def register_push_subscription(
    payload: PushSubscriptionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await notification_service.register_push_subscription(db, user.id, payload)
    return MessageResponse(message="Push subscription registered")
