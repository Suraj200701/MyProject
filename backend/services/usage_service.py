"""Credit metering for billable operations (lead search, website scan).

Why a reserve/settle model rather than "charge at the end"
---------------------------------------------------------
Charging after the work completes leaves a window where a caller with 1 credit
can trigger unlimited concurrent expensive operations — every request reads a
sufficient balance before any of them writes. Reserving up front closes that
window: the debit happens once, atomically, *before* the work starts.

    reserve(estimate)   -> debit now, raise 402 if the balance can't cover it
    ...do the work...
    settle(actual)      -> refund the unused part, or debit a small top-up
    release()           -> full refund when the work failed

Concurrency
-----------
`_lock_wallet()` uses `SELECT ... FOR UPDATE`, so two simultaneous searches for
the same organization serialize on the wallet row and cannot both pass the
balance check. Without the row lock, the classic lost-update race applies.

Ledger integrity
----------------
Every balance change writes a matching `Transaction` row with
`type=CREDIT_USAGE` and the resulting `balance_after`, so the ledger always
reconstructs the current balance. Reservations, settlements and refunds are all
individually visible rather than netted — an auditor can see what was reserved
vs. what was actually consumed.

Relationship to existing billing
--------------------------------
This module only ever *decrements* (or refunds) `CreditWallet.balance`;
top-ups and plan grants remain owned by `services/billing_service.py`, which is
untouched. `GET /billing/usage` computes `credits_used` as
`plan.credits_included - wallet.balance`, so it starts reporting real usage as
soon as this module debits — no change needed there.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.billing import CreditWallet, Transaction
from models.enums import TransactionType
from models.search import ApiProvider
from utils.exceptions import InsufficientCreditsError

if TYPE_CHECKING:
    # Type-only: importing the ORM model at runtime would create an import cycle
    # (models.user -> ... -> services), and this module only reads one attribute.
    from models.user import User

logger = logging.getLogger("leadmaster.usage")


@dataclass
class CreditReservation:
    """Handle for an in-flight reservation.

    `amount == 0` means metering was disabled or the operation was free; the
    settle/release helpers then become no-ops, so callers need no branching.
    """

    organization_id: uuid.UUID
    amount: int
    description: str
    settled: bool = False

    @property
    def is_active(self) -> bool:
        return self.amount > 0 and not self.settled


async def _lock_wallet(db: AsyncSession, organization_id: uuid.UUID) -> CreditWallet:
    """Fetches the wallet with a row-level write lock, creating it if absent.

    The lock is held until the surrounding transaction commits, which is what
    makes the check-then-debit sequence safe under concurrency.
    """
    stmt = select(CreditWallet).where(CreditWallet.organization_id == organization_id).with_for_update()
    wallet = (await db.execute(stmt)).scalar_one_or_none()
    if wallet is None:
        # A wallet is normally created at signup; this covers organizations
        # created before metering existed, and keeps the caller from 500ing.
        wallet = CreditWallet(organization_id=organization_id, balance=0)
        db.add(wallet)
        await db.flush()
    return wallet


def _record(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    credits_delta: int,
    balance_after: int,
    description: str,
) -> None:
    """Appends a CREDIT_USAGE ledger entry. Negative delta = consumption."""
    db.add(
        Transaction(
            organization_id=organization_id,
            type=TransactionType.CREDIT_USAGE,
            amount_cents=0,  # credits, not currency
            credits_delta=credits_delta,
            balance_after=balance_after,
            description=description[:500],
            created_at=datetime.now(UTC),
        )
    )


async def get_balance(db: AsyncSession, organization_id: uuid.UUID) -> int:
    """Current credit balance (0 when no wallet exists yet). No lock taken."""
    stmt = select(CreditWallet.balance).where(CreditWallet.organization_id == organization_id)
    return (await db.execute(stmt)).scalar_one_or_none() or 0


# --- Metering exemption ---------------------------------------------------


def is_metering_exempt(user: "User | None" = None) -> bool:
    """Whether this actor bypasses credit metering entirely.

    Exempt when **any** of these hold:

    * Metering is off globally (`CREDIT_METERING_ENABLED=false`), or the process
      is running in development with `CREDIT_METERING_DISABLED_IN_DEVELOPMENT`
      left at its default. Both are folded into `settings.credit_metering_active`.
    * The actor is a **superadmin**. Superadmins are platform operators, not
      tenants — they have no meaningful wallet of their own and are frequently
      acting inside someone else's organization, so charging that organization
      for an operator's search would corrupt the customer's usage figures as well
      as blocking the operator.

    Exemption is total: no balance check, no debit, no ledger entry. It is *not*
    "charge zero" — an operator's activity should leave the tenant's billing
    history untouched.

    Every other user follows the normal reserve/settle path unchanged.
    """
    if not settings.credit_metering_active:
        return True
    if user is not None and getattr(user, "is_superadmin", False):
        return True
    return False


# --- Cost estimation ------------------------------------------------------


async def get_provider_credit_cost(db: AsyncSession, provider_id: uuid.UUID) -> int:
    """Per-result credit cost for one provider, falling back to the default."""
    stmt = select(ApiProvider.credit_cost).where(ApiProvider.id == provider_id)
    cost = (await db.execute(stmt)).scalar_one_or_none()
    if cost is None:
        return settings.DEFAULT_SEARCH_CREDIT_COST_PER_RESULT
    return max(0, cost)


def estimate_search_cost(providers: list[ApiProvider], max_results_per_provider: int | None = None) -> int:
    """Worst-case cost of a search across the given providers.

    Deliberately pessimistic: reserving the maximum means a caller can never
    start work they cannot pay for. `settle_reservation` refunds the difference
    once the true result count is known, so over-reserving costs the user
    nothing.
    """
    cap = max_results_per_provider if max_results_per_provider is not None else settings.SEARCH_MAX_RESULTS_PER_PROVIDER
    total = 0
    for provider in providers:
        per_result = provider.credit_cost if provider.credit_cost is not None else settings.DEFAULT_SEARCH_CREDIT_COST_PER_RESULT
        total += max(0, per_result) * max(0, cap)
    return total


def calculate_search_actual_cost(results_by_provider: dict[uuid.UUID, int], providers: list[ApiProvider]) -> int:
    """Cost of the results actually produced, priced per originating provider."""
    cost_by_provider = {
        p.id: (p.credit_cost if p.credit_cost is not None else settings.DEFAULT_SEARCH_CREDIT_COST_PER_RESULT)
        for p in providers
    }
    total = 0
    for provider_id, count in results_by_provider.items():
        per_result = cost_by_provider.get(provider_id, settings.DEFAULT_SEARCH_CREDIT_COST_PER_RESULT)
        total += max(0, per_result) * max(0, count)
    return total


def scan_cost() -> int:
    """Flat credit cost of one website scan."""
    return max(0, settings.SCANNER_CREDITS_PER_SCAN)


# --- Reserve / settle / release -------------------------------------------


async def reserve_credits(
    db: AsyncSession,
    organization_id: uuid.UUID,
    amount: int,
    description: str,
    *,
    exempt: bool = False,
) -> CreditReservation:
    """Atomically debits `amount` credits up front.

    Raises `InsufficientCreditsError` (HTTP 402) when the balance cannot cover
    the amount, leaving the balance untouched.

    Pass `exempt=True` (from `is_metering_exempt`) to skip the balance check and
    the debit entirely — used for superadmins and for development. An exempt
    reservation has `amount == 0`, so the matching settle/release calls become
    no-ops and callers need no branching of their own.

    Does **not** commit — the reservation participates in the caller's
    transaction so a rollback also unwinds the debit.
    """
    if exempt or not settings.credit_metering_active or amount <= 0:
        return CreditReservation(organization_id=organization_id, amount=0, description=description)

    wallet = await _lock_wallet(db, organization_id)

    if wallet.balance < amount:
        # No ledger entry: nothing was consumed, and logging every rejected
        # attempt would let a caller flood the transactions table.
        raise InsufficientCreditsError(required=amount, available=wallet.balance)

    wallet.balance -= amount
    _record(
        db,
        organization_id=organization_id,
        credits_delta=-amount,
        balance_after=wallet.balance,
        description=f"Reserved {amount} credit(s) — {description}",
    )
    await db.flush()

    logger.info("Reserved %s credits for org %s (%s)", amount, organization_id, description)
    return CreditReservation(organization_id=organization_id, amount=amount, description=description)


async def settle_reservation(db: AsyncSession, reservation: CreditReservation, actual_amount: int) -> int:
    """Reconciles a reservation against actual usage. Returns credits charged.

    Refunds an over-reservation. If actual exceeded the estimate, charges the
    difference on a best-effort basis — the work is already done, so the
    shortfall is recorded (allowing the balance to reach 0) rather than
    failing the caller's request after the fact.
    """
    if not reservation.is_active:
        return 0

    actual_amount = max(0, actual_amount)
    difference = reservation.amount - actual_amount
    wallet = await _lock_wallet(db, reservation.organization_id)

    if difference > 0:
        wallet.balance += difference
        _record(
            db,
            organization_id=reservation.organization_id,
            credits_delta=difference,
            balance_after=wallet.balance,
            description=f"Refund {difference} unused credit(s) — {reservation.description}",
        )
    elif difference < 0:
        extra = min(-difference, wallet.balance)
        if extra > 0:
            wallet.balance -= extra
            _record(
                db,
                organization_id=reservation.organization_id,
                credits_delta=-extra,
                balance_after=wallet.balance,
                description=f"Additional {extra} credit(s) — {reservation.description}",
            )
        if extra < -difference:
            logger.warning(
                "Org %s used %s credits beyond its balance on: %s",
                reservation.organization_id,
                -difference - extra,
                reservation.description,
            )

    reservation.settled = True
    await db.flush()
    return actual_amount


async def release_reservation(db: AsyncSession, reservation: CreditReservation, reason: str = "operation failed") -> None:
    """Fully refunds a reservation — for reservations that were **committed**.

    ⚠️ Only call this when the reservation was committed in its own transaction
    (e.g. a Celery job that reserves, commits, then works). If the reservation
    is still pending in the caller's open transaction — which is the case for
    the synchronous `run_search`/`scan_website` paths — a `rollback()` already
    undoes the debit, and calling this as well would credit the balance twice,
    handing out free credits on every failure.

    Safe to call unconditionally (no-op for inactive reservations), so it can
    live in an `except`/`finally` block without extra guards.
    """
    if not reservation.is_active:
        return

    wallet = await _lock_wallet(db, reservation.organization_id)
    wallet.balance += reservation.amount
    _record(
        db,
        organization_id=reservation.organization_id,
        credits_delta=reservation.amount,
        balance_after=wallet.balance,
        description=f"Refund {reservation.amount} credit(s) — {reason}: {reservation.description}",
    )
    reservation.settled = True
    await db.flush()
    logger.info("Released %s credits for org %s (%s)", reservation.amount, reservation.organization_id, reason)


async def charge_credits(
    db: AsyncSession,
    organization_id: uuid.UUID,
    amount: int,
    description: str,
    *,
    exempt: bool = False,
) -> int:
    """Single-shot debit for operations with a known fixed cost.

    Equivalent to `reserve_credits` followed immediately by a settle at the
    same amount — used where the cost is knowable in advance (e.g. a website
    scan) and no reconciliation step is needed.
    """
    reservation = await reserve_credits(db, organization_id, amount, description, exempt=exempt)
    reservation.settled = True
    return reservation.amount
