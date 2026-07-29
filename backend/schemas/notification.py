"""Pydantic schemas for in-app notifications, delivery preferences, and
web-push subscriptions."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from models.enums import NotificationType


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: NotificationType
    title: str
    description: str | None = None
    created_at: datetime
    read_at: datetime | None = Field(default=None, exclude=True)

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def read(self) -> bool:
        return self.read_at is not None


class NotificationPreferenceOut(BaseModel):
    category: NotificationType
    email_enabled: bool
    push_enabled: bool
    in_app_enabled: bool

    model_config = {"from_attributes": True}


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    in_app_enabled: bool | None = None


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    p256dh_key: str
    auth_key: str
