"""Business logic for the platform-admin (superadmin-only) API surface.

Every function here operates across ALL organizations — there is no
tenant scoping. Callers must gate access via `api.deps.require_superadmin`
before reaching this module.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.billing import Payment, Subscription, SubscriptionPlan
from models.enums import PaymentStatus, SubscriptionStatus
from models.lead import Lead
from models.organization import Organization, OrganizationMember
from models.search import Search
from models.user import ActivityLog, User, UserSession
from schemas.admin import (
    AdminActivityLogOut,
    AdminDashboardStatsOut,
    AdminLeadModerationOut,
    AdminOrganizationOut,
    AdminPaymentOut,
    AdminSubscriptionOut,
    AdminUserOut,
)
from utils.exceptions import NotFoundError
from utils.pagination import Page, PaginationParams, paginate


async def get_platform_stats(db: AsyncSession) -> AdminDashboardStatsOut:
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    total_organizations = (await db.execute(select(func.count()).select_from(Organization))).scalar_one()
    total_leads = (await db.execute(select(func.count()).select_from(Lead))).scalar_one()
    total_searches = (await db.execute(select(func.count()).select_from(Search))).scalar_one()

    active_subscriptions_count = (
        await db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
        )
    ).scalar_one()

    mrr_stmt = (
        select(func.coalesce(func.sum(SubscriptionPlan.price_cents), 0))
        .select_from(Subscription)
        .join(SubscriptionPlan, Subscription.plan_id == SubscriptionPlan.id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    mrr_cents = (await db.execute(mrr_stmt)).scalar_one()

    return AdminDashboardStatsOut(
        total_users=total_users,
        total_organizations=total_organizations,
        total_leads_platform_wide=total_leads,
        mrr_cents=int(mrr_cents),
        active_subscriptions_count=active_subscriptions_count,
        total_searches_platform_wide=total_searches,
    )


async def _build_admin_user_out(db: AsyncSession, user: User) -> AdminUserOut:
    org_stmt = (
        select(Organization.name)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
    )
    organizations = [row[0] for row in (await db.execute(org_stmt)).all()]

    return AdminUserOut(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_superadmin=user.is_superadmin,
        role=user.role.name if user.role else None,
        organizations=organizations,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


async def list_users(
    db: AsyncSession,
    params: PaginationParams,
    search: str | None = None,
    is_active_filter: bool | None = None,
) -> Page[AdminUserOut]:
    stmt = select(User).options(selectinload(User.role)).order_by(User.created_at.desc())
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(func.lower(User.email).like(pattern))
    if is_active_filter is not None:
        stmt = stmt.where(User.is_active == is_active_filter)

    users, meta = await paginate(db, stmt, params)

    user_ids = [u.id for u in users]
    org_names_by_user: dict[uuid.UUID, list[str]] = {uid: [] for uid in user_ids}
    if user_ids:
        org_stmt = (
            select(OrganizationMember.user_id, Organization.name)
            .join(Organization, Organization.id == OrganizationMember.organization_id)
            .where(OrganizationMember.user_id.in_(user_ids))
        )
        for user_id, org_name in (await db.execute(org_stmt)).all():
            org_names_by_user.setdefault(user_id, []).append(org_name)

    items = [
        AdminUserOut(
            id=u.id,
            email=u.email,
            is_active=u.is_active,
            is_superadmin=u.is_superadmin,
            role=u.role.name if u.role else None,
            organizations=org_names_by_user.get(u.id, []),
            created_at=u.created_at,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]
    return Page(items=items, meta=meta)


async def set_user_active(db: AsyncSession, user_id: uuid.UUID, is_active: bool) -> AdminUserOut:
    """Suspends or reactivates a platform user. Suspending also revokes
    every active session (same revocation pattern as auth_service.logout)
    so the user is immediately signed out everywhere."""
    user = await db.get(User, user_id, options=[selectinload(User.role)])
    if user is None:
        raise NotFoundError("User not found")

    user.is_active = is_active
    if not is_active:
        user.deactivated_at = datetime.now(UTC)
        session_stmt = select(UserSession).where(
            UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
        )
        sessions = (await db.execute(session_stmt)).scalars().all()
        for s in sessions:
            s.revoked_at = datetime.now(UTC)
    else:
        user.deactivated_at = None

    await db.commit()
    await db.refresh(user, attribute_names=["role"])

    return await _build_admin_user_out(db, user)


async def _build_admin_organization_outs(
    db: AsyncSession, orgs: list[Organization]
) -> list[AdminOrganizationOut]:
    org_ids = [o.id for o in orgs]
    owner_ids = [o.owner_id for o in orgs]

    owner_emails: dict[uuid.UUID, str] = {}
    if owner_ids:
        owner_stmt = select(User.id, User.email).where(User.id.in_(owner_ids))
        owner_emails = dict((await db.execute(owner_stmt)).all())

    member_counts: dict[uuid.UUID, int] = {}
    if org_ids:
        count_stmt = (
            select(OrganizationMember.organization_id, func.count())
            .where(OrganizationMember.organization_id.in_(org_ids))
            .group_by(OrganizationMember.organization_id)
        )
        member_counts = dict((await db.execute(count_stmt)).all())

    subs_by_org: dict[uuid.UUID, Subscription] = {}
    if org_ids:
        sub_stmt = (
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(Subscription.organization_id.in_(org_ids))
        )
        for sub in (await db.execute(sub_stmt)).scalars().all():
            subs_by_org[sub.organization_id] = sub

    items = []
    for o in orgs:
        sub = subs_by_org.get(o.id)
        items.append(
            AdminOrganizationOut(
                id=o.id,
                name=o.name,
                owner_email=owner_emails.get(o.owner_id),
                member_count=member_counts.get(o.id, 0),
                plan_name=sub.plan.name if sub and sub.plan else None,
                subscription_status=sub.status if sub else None,
                created_at=o.created_at,
            )
        )
    return items


async def list_organizations(
    db: AsyncSession, params: PaginationParams, search: str | None = None
) -> Page[AdminOrganizationOut]:
    stmt = select(Organization).order_by(Organization.created_at.desc())
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(func.lower(Organization.name).like(pattern))

    orgs, meta = await paginate(db, stmt, params)
    items = await _build_admin_organization_outs(db, list(orgs))
    return Page(items=items, meta=meta)


async def get_organization_detail(db: AsyncSession, org_id: uuid.UUID) -> AdminOrganizationOut:
    org = await db.get(Organization, org_id)
    if org is None:
        raise NotFoundError("Organization not found")

    items = await _build_admin_organization_outs(db, [org])
    return items[0]


async def list_subscriptions(
    db: AsyncSession, params: PaginationParams, status_filter: SubscriptionStatus | None = None
) -> Page[AdminSubscriptionOut]:
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .order_by(Subscription.created_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(Subscription.status == status_filter)

    subs, meta = await paginate(db, stmt, params)

    org_ids = [s.organization_id for s in subs]
    org_names: dict[uuid.UUID, str] = {}
    if org_ids:
        org_stmt = select(Organization.id, Organization.name).where(Organization.id.in_(org_ids))
        org_names = dict((await db.execute(org_stmt)).all())

    items = [
        AdminSubscriptionOut(
            id=s.id,
            organization_id=s.organization_id,
            organization_name=org_names.get(s.organization_id),
            plan_name=s.plan.name if s.plan else None,
            price_cents=s.plan.price_cents if s.plan else None,
            status=s.status,
            current_period_start=s.current_period_start,
            current_period_end=s.current_period_end,
            cancel_at_period_end=s.cancel_at_period_end,
            created_at=s.created_at,
        )
        for s in subs
    ]
    return Page(items=items, meta=meta)


async def list_payments(
    db: AsyncSession, params: PaginationParams, status_filter: PaymentStatus | None = None
) -> Page[AdminPaymentOut]:
    stmt = select(Payment).order_by(Payment.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(Payment.status == status_filter)

    payments, meta = await paginate(db, stmt, params)

    org_ids = [p.organization_id for p in payments]
    org_names: dict[uuid.UUID, str] = {}
    if org_ids:
        org_stmt = select(Organization.id, Organization.name).where(Organization.id.in_(org_ids))
        org_names = dict((await db.execute(org_stmt)).all())

    items = [
        AdminPaymentOut(
            id=p.id,
            organization_id=p.organization_id,
            organization_name=org_names.get(p.organization_id),
            amount_cents=p.amount_cents,
            currency=p.currency,
            status=p.status,
            payment_method_type=p.payment_method_type,
            failure_reason=p.failure_reason,
            created_at=p.created_at,
        )
        for p in payments
    ]
    return Page(items=items, meta=meta)


async def list_leads_for_moderation(
    db: AsyncSession, params: PaginationParams
) -> Page[AdminLeadModerationOut]:
    stmt = select(Lead).options(selectinload(Lead.company)).order_by(Lead.created_at.desc())
    leads, meta = await paginate(db, stmt, params)

    org_ids = [lead.organization_id for lead in leads]
    org_names: dict[uuid.UUID, str] = {}
    if org_ids:
        org_stmt = select(Organization.id, Organization.name).where(Organization.id.in_(org_ids))
        org_names = dict((await db.execute(org_stmt)).all())

    items = [
        AdminLeadModerationOut(
            id=lead.id,
            company_name=lead.company.name if lead.company else None,
            organization_id=lead.organization_id,
            organization_name=org_names.get(lead.organization_id),
            status=lead.status,
            created_at=lead.created_at,
        )
        for lead in leads
    ]
    return Page(items=items, meta=meta)


async def delete_lead_admin(db: AsyncSession, lead_id: uuid.UUID) -> None:
    """Hard delete — admin override for removing abusive/spam content.
    Cascades to lead notes and activities via the FK ondelete rules."""
    lead = await db.get(Lead, lead_id)
    if lead is None:
        raise NotFoundError("Lead not found")

    await db.delete(lead)
    await db.commit()


async def list_activity_logs(
    db: AsyncSession,
    params: PaginationParams,
    user_id_filter: uuid.UUID | None = None,
    organization_id_filter: uuid.UUID | None = None,
    action_filter: str | None = None,
) -> Page[AdminActivityLogOut]:
    stmt = select(ActivityLog).order_by(ActivityLog.created_at.desc())
    if user_id_filter is not None:
        stmt = stmt.where(ActivityLog.user_id == user_id_filter)
    if organization_id_filter is not None:
        stmt = stmt.where(ActivityLog.organization_id == organization_id_filter)
    if action_filter:
        stmt = stmt.where(ActivityLog.action == action_filter)

    logs, meta = await paginate(db, stmt, params)

    user_ids = [log.user_id for log in logs if log.user_id]
    org_ids = [log.organization_id for log in logs if log.organization_id]

    user_emails: dict[uuid.UUID, str] = {}
    if user_ids:
        user_stmt = select(User.id, User.email).where(User.id.in_(user_ids))
        user_emails = dict((await db.execute(user_stmt)).all())

    org_names: dict[uuid.UUID, str] = {}
    if org_ids:
        org_stmt = select(Organization.id, Organization.name).where(Organization.id.in_(org_ids))
        org_names = dict((await db.execute(org_stmt)).all())

    items = [
        AdminActivityLogOut(
            id=log.id,
            user_id=log.user_id,
            user_email=user_emails.get(log.user_id) if log.user_id else None,
            organization_id=log.organization_id,
            organization_name=org_names.get(log.organization_id) if log.organization_id else None,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            ip_address=str(log.ip_address) if log.ip_address else None,
            created_at=log.created_at,
        )
        for log in logs
    ]
    return Page(items=items, meta=meta)
