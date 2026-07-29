"""Business logic for subscriptions, checkout, the credit ledger, and
inbound Stripe webhook processing.

Blocking calls into the `stripe` SDK are pushed onto a worker thread via
`asyncio.to_thread` so a slow/hanging Stripe API call can't stall the
event loop for other requests.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config.settings import settings
from models.billing import CreditWallet, Invoice, Payment, Subscription, SubscriptionPlan, Transaction, WebhookEvent
from models.enums import (
    InvoiceStatus,
    MemberStatus,
    PaymentStatus,
    SubscriptionStatus,
    TransactionType,
)
from models.organization import Organization, OrganizationMember
from models.search import Export, Search
from models.user import User
from payment import stripe_client
from utils.exceptions import BadRequestError, NotFoundError

# Mirrors src/components/billing/mock-data.ts CREDIT_PACKS so the frontend's
# preset pack ids resolve to a stable price/credit amount server-side (the
# client should never be trusted to send its own credit amount unchecked).
CREDIT_PACKS: dict[str, dict[str, int]] = {
    "c1": {"amount_cents": 2900, "credits": 1000},
    "c2": {"amount_cents": 11900, "credits": 5000},
    "c3": {"amount_cents": 39900, "credits": 20000},
}

# Fallback conversion rate for an arbitrary custom amount_cents that doesn't
# match a preset pack: priced at the smallest pack's per-credit rate (no
# volume discount for ad hoc amounts).
_FALLBACK_CENTS_PER_CREDIT = CREDIT_PACKS["c1"]["amount_cents"] / CREDIT_PACKS["c1"]["credits"]


# --- Internal helpers -------------------------------------------------


async def _get_subscription(db: AsyncSession, organization_id: uuid.UUID) -> Subscription | None:
    stmt = (
        select(Subscription)
        .where(Subscription.organization_id == organization_id)
        .options(selectinload(Subscription.plan))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_or_create_wallet(db: AsyncSession, organization_id: uuid.UUID) -> CreditWallet:
    stmt = select(CreditWallet).where(CreditWallet.organization_id == organization_id)
    wallet = (await db.execute(stmt)).scalar_one_or_none()
    if wallet is None:
        wallet = CreditWallet(organization_id=organization_id, balance=0)
        db.add(wallet)
        await db.flush()
    return wallet


def _resolve_topup(amount_cents: int | None, pack_id: str | None) -> tuple[int, int]:
    """Returns (amount_cents, credits) for a top-up request. Preset packs
    always win over a client-supplied amount so pricing can't be spoofed."""
    if pack_id:
        pack = CREDIT_PACKS.get(pack_id)
        if pack is None:
            raise BadRequestError(f"Unknown credit pack id '{pack_id}'")
        return pack["amount_cents"], pack["credits"]
    if amount_cents:
        credits = max(1, round(amount_cents / _FALLBACK_CENTS_PER_CREDIT))
        return amount_cents, credits
    raise BadRequestError("Provide either amount_cents or pack_id")


_STRIPE_STATUS_MAP = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.TRIALING,
    "past_due": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELED,
    "incomplete": SubscriptionStatus.INCOMPLETE,
    "incomplete_expired": SubscriptionStatus.CANCELED,
    "unpaid": SubscriptionStatus.PAST_DUE,
}


def _ts_to_dt(ts: int | None) -> datetime | None:
    return datetime.fromtimestamp(ts, tz=UTC) if ts else None


# --- Customer / checkout -----------------------------------------------


async def get_or_create_stripe_customer(db: AsyncSession, organization: Organization) -> str:
    """Returns the Stripe customer id for this organization, creating both
    the Stripe Customer and (if missing) a local Subscription row to hold
    it on first use."""
    subscription = await _get_subscription(db, organization.id)

    if subscription is None:
        free_plan = (
            await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "Free"))
        ).scalar_one_or_none()
        if free_plan is None:
            raise BadRequestError("No subscription plan is seeded. Run: python -m scripts.seed_data")
        subscription = Subscription(
            organization_id=organization.id, plan_id=free_plan.id, status=SubscriptionStatus.ACTIVE
        )
        db.add(subscription)
        await db.flush()
        subscription.plan = free_plan

    if subscription.provider_customer_id:
        return subscription.provider_customer_id

    owner = await db.get(User, organization.owner_id)
    owner_email = owner.email if owner else None
    if not owner_email:
        raise BadRequestError("Organization has no resolvable owner email for Stripe customer creation")

    customer = await asyncio.to_thread(stripe_client.create_customer, owner_email, organization.name)
    subscription.provider_customer_id = customer["id"]
    await db.commit()
    return subscription.provider_customer_id


async def create_plan_checkout(db: AsyncSession, organization: Organization, plan_id: uuid.UUID) -> str:
    """Creates a real Stripe Checkout Session for a subscription plan and
    returns the hosted checkout URL."""
    plan = await db.get(SubscriptionPlan, plan_id)
    if plan is None or not plan.is_active:
        raise NotFoundError("Subscription plan not found")
    if not plan.provider_price_id:
        # TODO(billing): SubscriptionPlan.provider_price_id is blank for the
        # seeded plans (see scripts/seed_data.py) — it needs to be populated
        # with a real Stripe Price id (created in the Stripe dashboard/API
        # once live keys exist) before checkout can work for this plan. Not
        # a schema change, just seed data that depends on real Stripe setup.
        raise BadRequestError(
            f"Plan '{plan.name}' has no Stripe price configured (provider_price_id is blank)"
        )

    customer_id = await get_or_create_stripe_customer(db, organization)
    success_url = f"{settings.FRONTEND_URL}/dashboard/billing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.FRONTEND_URL}/dashboard/billing?checkout=cancelled"
    metadata = {"organization_id": str(organization.id), "plan_id": str(plan.id), "kind": "plan_checkout"}

    session = await asyncio.to_thread(
        stripe_client.create_checkout_session,
        customer_id,
        plan.provider_price_id,
        success_url,
        cancel_url,
        "subscription",
        metadata,
    )
    return session["url"]


async def create_credit_topup_checkout(
    db: AsyncSession,
    organization: Organization,
    amount_cents: int | None = None,
    pack_id: str | None = None,
) -> str:
    """Creates a one-off Stripe Checkout Session for a credit top-up and
    returns the hosted checkout URL."""
    resolved_amount_cents, credits = _resolve_topup(amount_cents, pack_id)

    customer_id = await get_or_create_stripe_customer(db, organization)
    success_url = f"{settings.FRONTEND_URL}/dashboard/billing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.FRONTEND_URL}/dashboard/billing?checkout=cancelled"
    metadata = {"organization_id": str(organization.id), "credits": str(credits), "kind": "credit_topup"}

    session = await asyncio.to_thread(
        stripe_client.create_credit_topup_checkout,
        customer_id,
        resolved_amount_cents,
        success_url,
        cancel_url,
        metadata,
    )
    return session["url"]


# --- Webhook processing --------------------------------------------------


async def handle_webhook_event(db: AsyncSession, event: stripe.Event) -> None:
    """Idempotent webhook processor. The raw event is always recorded in
    WebhookEvent first (audit trail + idempotency key), and `processed_at`
    is only stamped once handling succeeds."""
    provider = "stripe"
    event_id = event["id"]
    event_type = event["type"]

    existing = (
        await db.execute(
            select(WebhookEvent).where(WebhookEvent.provider == provider, WebhookEvent.event_id == event_id)
        )
    ).scalar_one_or_none()

    if existing is not None and existing.processed_at is not None:
        return  # already processed — nothing to do (idempotency)

    if existing is None:
        try:
            payload = event.to_dict_recursive()
        except AttributeError:
            payload = dict(event)
        webhook_row = WebhookEvent(
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        db.add(webhook_row)
        await db.flush()
    else:
        webhook_row = existing

    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, obj)
    elif event_type == "invoice.paid":
        await _handle_invoice_paid(db, obj)
    elif event_type == "invoice.payment_failed":
        await _handle_invoice_payment_failed(db, obj)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_synced(db, obj, deleted=False)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_synced(db, obj, deleted=True)
    # Any other event type is recorded (above) but intentionally not acted on.

    webhook_row.processed_at = datetime.now(UTC)
    await db.commit()


async def _handle_checkout_completed(db: AsyncSession, session_obj: dict) -> None:
    metadata = session_obj.get("metadata") or {}
    org_id_raw = metadata.get("organization_id")
    if not org_id_raw:
        return  # not one of our checkout sessions (or metadata got stripped) — nothing we can attribute
    organization_id = uuid.UUID(org_id_raw)
    kind = metadata.get("kind")
    amount_total = session_obj.get("amount_total") or 0
    currency = session_obj.get("currency") or "usd"

    wallet = await _get_or_create_wallet(db, organization_id)

    if kind == "plan_checkout":
        plan_id = uuid.UUID(metadata["plan_id"]) if metadata.get("plan_id") else None
        plan = await db.get(SubscriptionPlan, plan_id) if plan_id else None

        subscription = await _get_subscription(db, organization_id)
        if subscription is None and plan is not None:
            subscription = Subscription(organization_id=organization_id, plan_id=plan.id)
            db.add(subscription)
            await db.flush()
        if subscription is not None:
            if plan is not None:
                subscription.plan_id = plan.id
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.provider_customer_id = session_obj.get("customer") or subscription.provider_customer_id
            subscription.provider_subscription_id = session_obj.get("subscription") or subscription.provider_subscription_id

        payment = Payment(
            organization_id=organization_id,
            subscription_id=subscription.id if subscription else None,
            provider_payment_intent_id=session_obj.get("payment_intent"),
            amount_cents=amount_total,
            currency=currency,
            status=PaymentStatus.SUCCEEDED,
            payment_method_type="card",
        )
        db.add(payment)
        await db.flush()

        credits_included = plan.credits_included if plan else 0
        wallet.balance += credits_included
        db.add(
            Transaction(
                organization_id=organization_id,
                payment_id=payment.id,
                type=TransactionType.SUBSCRIPTION_CHARGE,
                amount_cents=amount_total,
                credits_delta=credits_included,
                balance_after=wallet.balance,
                description=f"Subscription checkout — {plan.name if plan else plan_id}",
                created_at=datetime.now(UTC),
            )
        )

    elif kind == "credit_topup":
        credits = int(metadata.get("credits") or 0)

        payment = Payment(
            organization_id=organization_id,
            provider_payment_intent_id=session_obj.get("payment_intent"),
            amount_cents=amount_total,
            currency=currency,
            status=PaymentStatus.SUCCEEDED,
            payment_method_type="card",
        )
        db.add(payment)
        await db.flush()

        wallet.balance += credits
        db.add(
            Transaction(
                organization_id=organization_id,
                payment_id=payment.id,
                type=TransactionType.CREDIT_TOPUP,
                amount_cents=amount_total,
                credits_delta=credits,
                balance_after=wallet.balance,
                description=f"Credit top-up — {credits} credits",
                created_at=datetime.now(UTC),
            )
        )


async def _find_subscription_by_provider_ids(
    db: AsyncSession, *, subscription_id: str | None = None, customer_id: str | None = None
) -> Subscription | None:
    stmt = select(Subscription)
    if subscription_id:
        row = (await db.execute(stmt.where(Subscription.provider_subscription_id == subscription_id))).scalar_one_or_none()
        if row is not None:
            return row
    if customer_id:
        return (await db.execute(stmt.where(Subscription.provider_customer_id == customer_id))).scalar_one_or_none()
    return None


async def _handle_invoice_paid(db: AsyncSession, invoice_obj: dict) -> None:
    subscription = await _find_subscription_by_provider_ids(
        db, subscription_id=invoice_obj.get("subscription"), customer_id=invoice_obj.get("customer")
    )
    if subscription is None:
        return  # can't attribute this invoice to any organization — nothing to record

    provider_invoice_id = invoice_obj.get("id")
    existing = None
    if provider_invoice_id:
        existing = (
            await db.execute(select(Invoice).where(Invoice.provider_invoice_id == provider_invoice_id))
        ).scalar_one_or_none()

    invoice_number = invoice_obj.get("number") or f"INV-{provider_invoice_id}"
    amount_cents = invoice_obj.get("amount_paid") or 0
    currency = invoice_obj.get("currency") or "usd"
    period_start = _ts_to_dt(invoice_obj.get("period_start"))
    period_end = _ts_to_dt(invoice_obj.get("period_end"))
    invoice_pdf_url = invoice_obj.get("invoice_pdf")

    if existing is not None:
        existing.status = InvoiceStatus.PAID
        existing.amount_cents = amount_cents
        existing.invoice_pdf_url = invoice_pdf_url
        existing.period_start = period_start
        existing.period_end = period_end
    else:
        db.add(
            Invoice(
                organization_id=subscription.organization_id,
                subscription_id=subscription.id,
                provider_invoice_id=provider_invoice_id,
                invoice_number=invoice_number,
                amount_cents=amount_cents,
                currency=currency,
                status=InvoiceStatus.PAID,
                invoice_pdf_url=invoice_pdf_url,
                period_start=period_start,
                period_end=period_end,
            )
        )


async def _handle_invoice_payment_failed(db: AsyncSession, invoice_obj: dict) -> None:
    subscription = await _find_subscription_by_provider_ids(
        db, subscription_id=invoice_obj.get("subscription"), customer_id=invoice_obj.get("customer")
    )
    if subscription is None:
        return

    amount_due = invoice_obj.get("amount_due") or 0
    currency = invoice_obj.get("currency") or "usd"

    db.add(
        Payment(
            organization_id=subscription.organization_id,
            subscription_id=subscription.id,
            provider_payment_intent_id=invoice_obj.get("payment_intent"),
            amount_cents=amount_due,
            currency=currency,
            status=PaymentStatus.FAILED,
            payment_method_type="card",
            failure_reason="Stripe invoice payment failed",
        )
    )

    if subscription.status != SubscriptionStatus.CANCELED:
        subscription.status = SubscriptionStatus.PAST_DUE


async def _handle_subscription_synced(db: AsyncSession, sub_obj: dict, *, deleted: bool) -> None:
    subscription = await _find_subscription_by_provider_ids(
        db, subscription_id=sub_obj.get("id"), customer_id=sub_obj.get("customer")
    )
    if subscription is None:
        return

    subscription.status = SubscriptionStatus.CANCELED if deleted else _STRIPE_STATUS_MAP.get(
        sub_obj.get("status"), subscription.status
    )
    subscription.current_period_start = _ts_to_dt(sub_obj.get("current_period_start")) or subscription.current_period_start
    subscription.current_period_end = _ts_to_dt(sub_obj.get("current_period_end")) or subscription.current_period_end
    subscription.cancel_at_period_end = bool(sub_obj.get("cancel_at_period_end", False))


# --- Usage / history -----------------------------------------------------


async def get_usage(db: AsyncSession, organization: Organization) -> dict:
    subscription = await _get_subscription(db, organization.id)
    plan = subscription.plan if subscription else None

    wallet = await _get_or_create_wallet(db, organization.id)
    credits_limit = plan.credits_included if plan else 0
    credits_used = max(0, credits_limit - wallet.balance)

    seats_used = (
        await db.execute(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization.id,
                OrganizationMember.status == MemberStatus.ACTIVE,
            )
        )
    ).scalar_one()
    seats_limit = plan.seats_included if plan else 0

    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    searches_this_month = (
        await db.execute(
            select(func.count())
            .select_from(Search)
            .where(Search.organization_id == organization.id, Search.created_at >= month_start)
        )
    ).scalar_one()

    exports_this_month = (
        await db.execute(
            select(func.count())
            .select_from(Export)
            .where(Export.organization_id == organization.id, Export.created_at >= month_start)
        )
    ).scalar_one()

    return {
        "credits_used": credits_used,
        "credits_limit": credits_limit,
        "seats_used": seats_used,
        "seats_limit": seats_limit,
        "searches_this_month": searches_this_month,
        "exports_this_month": exports_this_month,
    }


async def get_subscription(db: AsyncSession, organization: Organization) -> Subscription | None:
    return await _get_subscription(db, organization.id)


async def refund_payment(db: AsyncSession, organization: Organization, payment_id: uuid.UUID) -> Payment:
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.organization_id != organization.id:
        raise NotFoundError("Payment not found")
    if payment.status != PaymentStatus.SUCCEEDED:
        raise BadRequestError("Only succeeded payments can be refunded")
    if not payment.provider_payment_intent_id:
        raise BadRequestError("Payment has no associated Stripe payment intent to refund")

    await asyncio.to_thread(stripe_client.create_refund, payment.provider_payment_intent_id)

    payment.status = PaymentStatus.REFUNDED

    wallet = await _get_or_create_wallet(db, organization.id)
    db.add(
        Transaction(
            organization_id=organization.id,
            payment_id=payment.id,
            type=TransactionType.REFUND,
            amount_cents=-payment.amount_cents,
            credits_delta=0,
            balance_after=wallet.balance,
            description=f"Refund for payment {payment.id}",
            created_at=datetime.now(UTC),
        )
    )

    await db.commit()
    await db.refresh(payment)
    return payment
