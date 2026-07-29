"""Pydantic schemas for the platform-admin API surface (superadmin only).

These are platform-wide views across every organization — distinct from
the org-scoped schemas elsewhere (schemas/user.py, schemas/billing.py,
...) which are always implicitly filtered to the caller's own workspace.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from models.enums import LeadStatus, PaymentStatus, RoleName, SubscriptionStatus


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    is_active: bool
    is_superadmin: bool
    role: RoleName | None = None
    organizations: list[str] = []
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdminUserStatusUpdate(BaseModel):
    is_active: bool


class AdminOrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_email: EmailStr | None = None
    member_count: int
    plan_name: str | None = None
    subscription_status: SubscriptionStatus | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminSubscriptionOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str | None = None
    plan_name: str | None = None
    price_cents: int | None = None
    status: SubscriptionStatus
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminPaymentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str | None = None
    amount_cents: int
    currency: str
    status: PaymentStatus
    payment_method_type: str | None = None
    failure_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminLeadModerationOut(BaseModel):
    """Minimal, spot-check-friendly view of a lead for abuse moderation —
    intentionally does not expose full contact PII."""

    id: uuid.UUID
    company_name: str | None = None
    organization_id: uuid.UUID
    organization_name: str | None = None
    status: LeadStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminActivityLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    organization_id: uuid.UUID | None = None
    organization_name: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminDashboardStatsOut(BaseModel):
    total_users: int
    total_organizations: int
    total_leads_platform_wide: int
    mrr_cents: int
    active_subscriptions_count: int
    total_searches_platform_wide: int
