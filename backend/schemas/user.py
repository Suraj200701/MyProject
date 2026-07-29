"""Pydantic schemas for users, profiles, and auth payloads."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class ProfileOut(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    job_title: str | None = None
    timezone: str
    locale: str

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    phone: str | None = None
    is_active: bool
    is_email_verified: bool
    two_factor_enabled: bool
    created_at: datetime
    last_login_at: datetime | None = None
    role: RoleOut | None = None
    profile: ProfileOut | None = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    job_title: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str | None = None
    locale: str | None = None


def _validate_password_strength(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not any(c.isupper() for c in value):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.isdigit() for c in value):
        raise ValueError("Password must contain at least one digit")
    return value


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = Field(min_length=1, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class VerifyEmailRequest(BaseModel):
    token: str


class OtpRequestSchema(BaseModel):
    email: EmailStr
    purpose: str = "login"


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)
    purpose: str = "login"


class SessionOut(BaseModel):
    id: uuid.UUID
    device_label: str | None
    ip_address: str | None
    location: str | None
    last_active_at: datetime
    created_at: datetime
    is_current: bool = False

    model_config = {"from_attributes": True}
