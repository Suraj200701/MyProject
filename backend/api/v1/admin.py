"""Platform-admin (superadmin-only) endpoints — every route is gated by
`require_superadmin` and operates across ALL organizations."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import require_superadmin
from database.session import get_db
from models.enums import PaymentStatus, SubscriptionStatus
from schemas.admin import (
    AdminActivityLogOut,
    AdminDashboardStatsOut,
    AdminLeadModerationOut,
    AdminOrganizationOut,
    AdminPaymentOut,
    AdminSubscriptionOut,
    AdminUserOut,
    AdminUserStatusUpdate,
)
from schemas.common import MessageResponse
from services import admin_service
from utils.pagination import Page, PaginationParams, pagination_params

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_superadmin)])


@router.get("/stats", response_model=AdminDashboardStatsOut)
async def get_stats(db: AsyncSession = Depends(get_db)):
    return await admin_service.get_platform_stats(db)


@router.get("/users", response_model=Page[AdminUserOut])
async def list_users(
    search: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    params: PaginationParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_users(db, params, search=search, is_active_filter=is_active)


@router.patch("/users/{user_id}/status", response_model=AdminUserOut)
async def set_user_status(
    user_id: uuid.UUID, payload: AdminUserStatusUpdate, db: AsyncSession = Depends(get_db)
):
    return await admin_service.set_user_active(db, user_id, payload.is_active)


@router.get("/organizations", response_model=Page[AdminOrganizationOut])
async def list_organizations(
    search: str | None = Query(default=None),
    params: PaginationParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_organizations(db, params, search=search)


@router.get("/organizations/{org_id}", response_model=AdminOrganizationOut)
async def get_organization(org_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await admin_service.get_organization_detail(db, org_id)


@router.get("/subscriptions", response_model=Page[AdminSubscriptionOut])
async def list_subscriptions(
    status: SubscriptionStatus | None = Query(default=None),
    params: PaginationParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_subscriptions(db, params, status_filter=status)


@router.get("/payments", response_model=Page[AdminPaymentOut])
async def list_payments(
    status: PaymentStatus | None = Query(default=None),
    params: PaginationParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_payments(db, params, status_filter=status)


@router.get("/leads", response_model=Page[AdminLeadModerationOut])
async def list_leads(
    params: PaginationParams = Depends(pagination_params), db: AsyncSession = Depends(get_db)
):
    return await admin_service.list_leads_for_moderation(db, params)


@router.delete("/leads/{lead_id}", response_model=MessageResponse)
async def delete_lead(lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await admin_service.delete_lead_admin(db, lead_id)
    return MessageResponse(message="Lead deleted")


@router.get("/activity-logs", response_model=Page[AdminActivityLogOut])
async def list_activity_logs(
    user_id: uuid.UUID | None = Query(default=None),
    organization_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    params: PaginationParams = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
):
    return await admin_service.list_activity_logs(
        db, params, user_id_filter=user_id, organization_id_filter=organization_id, action_filter=action
    )
