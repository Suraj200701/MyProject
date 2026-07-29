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
from models.user import User
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
    """Route dependency factory: `Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN))`."""

    async def _checker(membership: OrganizationMember = Depends(get_current_membership)) -> OrganizationMember:
        if membership.role.name not in allowed_roles:
            raise ForbiddenError(
                f"This action requires one of the following roles: {', '.join(r.value for r in allowed_roles)}"
            )
        return membership

    return _checker
