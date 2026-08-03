"""Shared FastAPI dependencies: current user, current organization, and
role-based access control gates."""

import uuid
from collections.abc import Callable

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.jwt import TokenError, TokenType, decode_token
from database.session import get_db
from models.enums import RoleName
from models.organization import Organization, OrganizationMember
from models.user import Permission, RolePermission, User
from utils.exceptions import ForbiddenError, NotFoundError, UnauthorizedError

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")

    try:
        payload = decode_token(credentials.credentials, TokenType.ACCESS)
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user_id = payload.get("sub")
    stmt = (
        select(User)
        .where(User.id == uuid.UUID(user_id))
        .options(selectinload(User.role), selectinload(User.profile))
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    return user


async def get_current_active_verified_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_email_verified:
        raise ForbiddenError("Please verify your email address to continue")
    return user


def require_superadmin(user: User = Depends(get_current_user)) -> User:
    if not user.is_superadmin:
        raise ForbiddenError("Superadmin access required")
    return user


async def get_current_organization(
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """Resolves the active organization for this request.

    If the client sends X-Organization-Id, that membership is validated.
    Otherwise we fall back to the user's first (oldest) membership —
    covers the common single-workspace case without requiring the
    frontend to always send the header.
    """
    stmt = (
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.id)
        .options(selectinload(OrganizationMember.organization), selectinload(OrganizationMember.role))
        .order_by(OrganizationMember.created_at)
    )
    if x_organization_id:
        stmt = stmt.where(OrganizationMember.organization_id == uuid.UUID(x_organization_id))

    membership = (await db.execute(stmt)).scalars().first()
    if membership is None:
        raise NotFoundError("No accessible organization found for this user")

    return membership.organization


async def get_current_membership(
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationMember:
    stmt = (
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.id)
        .options(selectinload(OrganizationMember.role))
        .order_by(OrganizationMember.created_at)
    )
    if x_organization_id:
        stmt = stmt.where(OrganizationMember.organization_id == uuid.UUID(x_organization_id))

    membership = (await db.execute(stmt)).scalars().first()
    if membership is None:
        raise NotFoundError("No accessible organization found for this user")
    return membership


def require_org_role(*allowed_roles: RoleName) -> Callable:
    """Route dependency factory: `Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN))`.

    Superadmins bypass the check, matching `require_permission` below. Without
    this, the two authorization gates disagreed: a platform operator could
    export an organization's leads (permission gate) but not read its billing
    settings (role gate), purely because of which gate a route happened to use.
    """

    async def _checker(
        membership: OrganizationMember = Depends(get_current_membership),
        user: User = Depends(get_current_user),
    ) -> OrganizationMember:
        if user.is_superadmin:
            return membership
        if membership.role.name not in allowed_roles:
            raise ForbiddenError(
                f"This action requires one of the following roles: {', '.join(r.value for r in allowed_roles)}"
            )
        return membership

    return _checker


def require_permission(code: str) -> Callable:
    """Route dependency factory gating on a seeded `Permission.code`.

    Prefer this over `require_org_role` when a capability is already modelled as
    a permission: the role -> permission mapping in `scripts/seed_data.py`
    becomes the single source of truth, so granting a role a new capability is a
    seed change rather than an edit to every route that allows it.

    Superadmins bypass the check — they are platform operators, not members of
    the organization whose role grants the permission.

    Usage: `Depends(require_permission("leads.export"))`
    """

    async def _checker(
        membership: OrganizationMember = Depends(get_current_membership),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> OrganizationMember:
        if user.is_superadmin:
            return membership

        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == membership.role_id, Permission.code == code)
        )
        if (await db.execute(stmt)).scalar_one_or_none() is None:
            raise ForbiddenError(
                f"Your role ({membership.role.name.value}) does not have the '{code}' permission"
            )
        return membership

    return _checker
