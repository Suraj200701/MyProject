"""Pydantic schemas for the Settings API: profile, organization, personal
API keys, the generic key-value settings store, and backup snapshot
metadata."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    job_title: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str | None = None
    locale: str | None = None


class ProfileOut(BaseModel):
    """Combines `User` (email, phone) and `UserProfile` (everything else)
    columns — built explicitly in the route, not via `from_attributes`,
    since the two live on separate tables."""

    id: uuid.UUID
    email: EmailStr
    phone: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
    job_title: str | None = None
    timezone: str
    locale: str


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    industry: str | None = None
    company_size: str | None = None
    website: str | None = None
    logo_url: str | None = None
    timezone: str
    locale: str
    # Additive: the Team page shows when the workspace was created. Reading it
    # from the Organization row is the only way to show a real date there.
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=100)
    company_size: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=255)
    timezone: str | None = None
    locale: str | None = None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class ApiKeyOut(BaseModel):
    """`masked` is reconstructed for display. At creation time it includes
    the real trailing 4 characters of the key (still in memory); for every
    later listing it only shows the stored `key_prefix` followed by dots,
    since the full key is never persisted and the true suffix can't be
    recovered afterwards."""

    id: uuid.UUID
    name: str
    key_prefix: str
    masked: str
    last_used_at: datetime | None = None
    created_at: datetime


class ApiKeyCreateResponse(ApiKeyOut):
    """Returned ONLY once, immediately after creation — the sole moment the
    full plaintext key is ever available. It is never stored (only a
    bcrypt hash + short prefix persist) and can never be retrieved again."""

    key: str


class SettingUpdate(BaseModel):
    key: str = Field(min_length=1, max_length=150)
    value: dict[str, Any]


class SettingOut(BaseModel):
    scope: str
    key: str
    value: dict[str, Any]


class BackupSnapshotCreate(BaseModel):
    label: str | None = Field(default=None, max_length=150)


class BackupSnapshotOut(BaseModel):
    id: uuid.UUID
    label: str
    size_bytes: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
