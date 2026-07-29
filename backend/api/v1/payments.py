"""Billing & subscriptions endpoints: plans, current subscription, usage,
Stripe checkout, payment/transaction/invoice history, refunds, and the
inbound Stripe webhook."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_membership, get_current_organization, get_current_user
from database.session import get_db
from models.billing import Invoice, Payment, SubscriptionPlan, Transaction
from models.enums import RoleName
from models.organization import Organization, OrganizationMember
from payment import stripe_client
from schemas.billing import (
    CheckoutSessionOut,
    CheckoutSessionRequest,
    CreditTopupRequest,
    InvoiceOut,
    PaymentOut,
    PlanOut,
    SubscriptionOut,
    TransactionOut,
    UsageOut,
)
from schemas.common import MessageResponse
from services import billing_service
from utils.exceptions import BadRequestError, NotFoundError
from utils.pagination import Page, PageMeta, PaginationParams, pagination_params, paginate

router = APIRouter(prefix="/billing", tags=["Billing"])

_require_billing_manager = require_org_role = None  # placeholder replaced below to avoid unused-import lint noise
from api.deps import require_org_role  # noqa: E402  (kept local for clarity next to its usage)


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(
    user=Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.price_cents)
    plans = (await db.execute(stmt)).scalars().all()
    return [PlanOut.model_validate(p) for p in plans]


@router.get("/subscription", response_model=SubscriptionOut | None)
async def get_subscription(
    user=Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    subscription = await billing_service.get_subscription(db, organization)
    if subscription is None:
        return None
    return SubscriptionOut.model_validate(subscription)


@router.get("/usage", response_model=UsageOut)
async def get_usage(
    user=Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    usage = await billing_service.get_usage(db, organization)
    return UsageOut(**usage)


@router.post("/checkout", response_model=CheckoutSessionOut)
async def create_checkout(
    payload: CheckoutSessionRequest,
    user=Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    membership: OrganizationMember = Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    checkout_url = await billing_service.create_plan_checkout(db, organization, payload.plan_id)
    return CheckoutSessionOut(checkout_url=checkout_url)


@router.post("/credits/checkout", response_model=CheckoutSessionOut)
async def create_credit_topup_checkout(
    payload: CreditTopupRequest,
    user=Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    membership: OrganizationMember = Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    checkout_url = await billing_service.create_credit_topup_checkout(
        db, organization, amount_cents=payload.amount_cents, pack_id=payload.pack_id
    )
    return CheckoutSessionOut(checkout_url=checkout_url)


@router.get("/payments", response_model=Page[PaymentOut])
async def list_payments(
    user=Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    params: PaginationParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Payment).where(Payment.organization_id == organization.id).order_by(Payment.created_at.desc())
    rows, meta = await paginate(db, stmt, params)
    return Page[PaymentOut](items=[PaymentOut.model_validate(r) for r in rows], meta=meta)


@router.get("/transactions", response_model=Page[TransactionOut])
async def list_transactions(
    user=Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    params: PaginationParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Transaction)
        .where(Transaction.organization_id == organization.id)
        .order_by(Transaction.created_at.desc())
    )
    rows, meta = await paginate(db, stmt, params)
    return Page[TransactionOut](items=[TransactionOut.model_validate(r) for r in rows], meta=meta)


@router.get("/invoices", response_model=Page[InvoiceOut])
async def list_invoices(
    user=Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    params: PaginationParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Invoice).where(Invoice.organization_id == organization.id).order_by(Invoice.created_at.desc())
    rows, meta = await paginate(db, stmt, params)
    return Page[InvoiceOut](items=[InvoiceOut.model_validate(r) for r in rows], meta=meta)


@router.post("/payments/{payment_id}/refund", response_model=PaymentOut)
async def refund_payment(
    payment_id: uuid.UUID,
    user=Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    membership: OrganizationMember = Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    payment = await billing_service.refund_payment(db, organization, payment_id)
    return PaymentOut.model_validate(payment)


@router.post("/webhook", response_model=MessageResponse)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Stripe calls this endpoint directly — intentionally has no auth
    dependency. Trust is instead established by verifying the
    `Stripe-Signature` header against STRIPE_WEBHOOK_SECRET."""
    payload_bytes = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # construct_webhook_event raises BadRequestError (-> HTTP 400) on a
    # missing/invalid signature or an unconfigured webhook secret, which is
    # exactly the response Stripe expects for a rejected webhook.
    event = stripe_client.construct_webhook_event(payload_bytes, sig_header)

    await billing_service.handle_webhook_event(db, event)
    return MessageResponse(message="ok")
