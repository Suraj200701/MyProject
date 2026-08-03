"""Pydantic schemas for the billing & subscriptions API surface."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from models.enums import BillingInterval, InvoiceStatus, PaymentStatus, SubscriptionStatus, TransactionType


class PlanOut(BaseModel):
    id: uuid.UUID
    name: str
    price_cents: int
    currency: str
    billing_interval: BillingInterval
    credits_included: int
    seats_included: int
    features: list[str] | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    plan: PlanOut
    status: SubscriptionStatus
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool

    model_config = {"from_attributes": True}


class UsageOut(BaseModel):
    credits_used: int
    credits_limit: int
    seats_used: int
    seats_limit: int
    searches_this_month: int
    exports_this_month: int


class PaymentOut(BaseModel):
    id: uuid.UUID
    amount_cents: int
    currency: str
    status: PaymentStatus
    payment_method_type: str | None = None
    failure_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionOut(BaseModel):
    id: uuid.UUID
    type: TransactionType
    amount_cents: int
    credits_delta: int
    balance_after: int
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceOut(BaseModel):
    id: uuid.UUID
    invoice_number: str
    amount_cents: int
    currency: str
    status: InvoiceStatus
    invoice_pdf_url: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckoutSessionRequest(BaseModel):
    plan_id: uuid.UUID


class CreditTopupRequest(BaseModel):
    """Either an explicit `amount_cents`, or a preset pack id matching the
    frontend's CREDIT_PACKS (see src/components/billing/mock-data.ts)."""

    amount_cents: int | None = Field(default=None, ge=100)
    pack_id: str | None = None


class CheckoutSessionOut(BaseModel):
    checkout_url: str


class CreditPackOut(BaseModel):
    """One purchasable credit bundle.

    Prices are returned in minor units so the client formats them with the same
    currency logic it uses for invoices, rather than parsing a display string.
    """

    id: str
    credits: int
    amount_cents: int
    currency: str = "usd"
