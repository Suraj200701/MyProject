"""Thin wrapper around the `stripe` Python SDK.

`settings.STRIPE_SECRET_KEY` is allowed to be blank in local/dev
environments where the user hasn't supplied real Stripe credentials yet.
We must not crash at import time in that case — `stripe.api_key` is only
set (lazily) the moment one of these functions is actually called, and if
the key is still blank at that point we raise a clear `BadRequestError`
instead of letting a confusing stripe library exception bubble up.

Every function here performs a REAL call against the Stripe API via the
`stripe` package — nothing is mocked or stubbed. It simply cannot succeed
until the user fills in STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET in .env.
"""

import stripe

from config.settings import settings
from utils.exceptions import BadRequestError

_NOT_CONFIGURED_MSG = "Stripe is not configured — set STRIPE_SECRET_KEY in .env"


def _ensure_configured() -> None:
    """Lazily points the stripe SDK at our secret key. Raises a friendly
    error instead of letting stripe.error.AuthenticationError (or similar)
    bubble up when no key has been provided yet."""
    if not settings.STRIPE_SECRET_KEY:
        raise BadRequestError(_NOT_CONFIGURED_MSG)
    stripe.api_key = settings.STRIPE_SECRET_KEY


def create_customer(email: str, name: str | None = None) -> stripe.Customer:
    """Creates a Stripe Customer for an organization/user."""
    _ensure_configured()
    try:
        return stripe.Customer.create(email=email, name=name)
    except stripe.error.StripeError as exc:
        raise BadRequestError(f"Stripe error creating customer: {exc.user_message or str(exc)}") from exc


def create_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    mode: str = "subscription",
    metadata: dict | None = None,
) -> stripe.checkout.Session:
    """Creates a real Stripe-hosted Checkout Session for a subscription
    (or one-off) purchase against an existing Stripe price.

    `metadata` is attached to the Session (and, for subscription mode,
    Stripe copies it onto the resulting Subscription too) so the webhook
    handler can identify which organization/plan a completed session
    belongs to without extra lookups.
    """
    _ensure_configured()
    try:
        return stripe.checkout.Session.create(
            customer=customer_id,
            mode=mode,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata or {},
            subscription_data={"metadata": metadata or {}} if mode == "subscription" else None,
        )
    except stripe.error.StripeError as exc:
        raise BadRequestError(f"Stripe error creating checkout session: {exc.user_message or str(exc)}") from exc


def create_credit_topup_checkout(
    customer_id: str,
    amount_cents: int,
    success_url: str,
    cancel_url: str,
    metadata: dict | None = None,
) -> stripe.checkout.Session:
    """One-off (mode='payment') Checkout Session for a credit top-up, priced
    ad hoc via `price_data` rather than a pre-created Stripe Price object
    since top-up amounts are chosen freely by the customer.

    `metadata` (e.g. organization_id, credits granted) is attached to the
    Session so `checkout.session.completed` can credit the right wallet.
    """
    _ensure_configured()
    try:
        return stripe.checkout.Session.create(
            customer=customer_id,
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "LeadMaster AI credit top-up"},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata or {},
        )
    except stripe.error.StripeError as exc:
        raise BadRequestError(f"Stripe error creating credit top-up checkout: {exc.user_message or str(exc)}") from exc


def construct_webhook_event(payload_bytes: bytes, sig_header: str | None) -> stripe.Event:
    """Verifies the inbound webhook's signature against
    settings.STRIPE_WEBHOOK_SECRET and returns the parsed stripe.Event.

    This is a real, security-critical signature check — never skipped —
    so a forged request without a valid signature is rejected with a 400
    rather than being processed.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BadRequestError("Stripe webhooks are not configured — set STRIPE_WEBHOOK_SECRET in .env")
    if not sig_header:
        raise BadRequestError("Missing Stripe-Signature header")
    try:
        return stripe.Webhook.construct_event(payload_bytes, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError as exc:
        raise BadRequestError("Invalid webhook payload") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise BadRequestError("Invalid webhook signature") from exc


def create_refund(payment_intent_id: str, amount_cents: int | None = None) -> stripe.Refund:
    """Refunds a payment, in full unless `amount_cents` is given."""
    _ensure_configured()
    try:
        kwargs = {"payment_intent": payment_intent_id}
        if amount_cents is not None:
            kwargs["amount"] = amount_cents
        return stripe.Refund.create(**kwargs)
    except stripe.error.StripeError as exc:
        raise BadRequestError(f"Stripe error creating refund: {exc.user_message or str(exc)}") from exc
