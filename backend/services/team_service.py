"""Business logic for team membership and invitations."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.security import generate_token, hash_password, verify_password
from models.enums import MemberStatus, RoleName
from models.organization import Organization, OrganizationMember, TeamInvitation
from models.user import Permission, Role, User, UserProfile, UserSession
from notifications.email_service import send_team_invitation_email
from schemas.team import MemberOut
from utils.exceptions import BadRequestError, ConflictError, NotFoundError

INVITATION_EXPIRE_DAYS = 7


async def _get_role_by_name(db: AsyncSession, name: str) -> Role:
    stmt = select(Role).where(Role.name == RoleName(name))
    role = (await db.execute(stmt)).scalar_one_or_none()
    if role is None:
        raise BadRequestError(f"Unknown role: {name}")
    return role


async def list_members(db: AsyncSession, organization_id: uuid.UUID) -> list[MemberOut]:
    stmt = (
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .options(
            selectinload(OrganizationMember.user).selectinload(User.profile),
            selectinload(OrganizationMember.role),
        )
        .order_by(OrganizationMember.created_at)
    )
    members = (await db.execute(stmt)).scalars().all()

    out = []
    for m in members:
        last_active = None
        session_stmt = (
            select(UserSession.last_active_at)
            .where(UserSession.user_id == m.user_id, UserSession.revoked_at.is_(None))
            .order_by(UserSession.last_active_at.desc())
            .limit(1)
        )
        last_active = (await db.execute(session_stmt)).scalar_one_or_none()

        out.append(
            MemberOut(
                id=m.id,
                user_id=m.user_id,
                name=m.user.profile.full_name if m.user.profile else None,
                email=m.user.email,
                avatar_url=m.user.profile.avatar_url if m.user.profile else None,
                role=m.role.name.value,
                status=m.status.value,
                joined_at=m.joined_at,
                last_active=last_active or m.user.last_login_at,
            )
        )
    return out


async def invite_member(
    db: AsyncSession, organization: Organization, inviter: User, email: str, role_name: str
) -> TeamInvitation:
    role = await _get_role_by_name(db, role_name)

    existing_member_stmt = (
        select(OrganizationMember)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization.id, User.email == email.lower())
    )
    if (await db.execute(existing_member_stmt)).scalar_one_or_none():
        raise ConflictError("This person is already a member of your workspace")

    token = generate_token(24)
    invitation = TeamInvitation(
        organization_id=organization.id,
        email=email.lower(),
        role_id=role.id,
        invited_by_id=inviter.id,
        token_hash=hash_password(token),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(days=INVITATION_EXPIRE_DAYS),
    )
    db.add(invitation)

    existing_user_stmt = select(User).where(User.email == email.lower())
    existing_user = (await db.execute(existing_user_stmt)).scalar_one_or_none()
    if existing_user:
        db.add(
            OrganizationMember(
                organization_id=organization.id,
                user_id=existing_user.id,
                role_id=role.id,
                status=MemberStatus.INVITED,
                invited_at=datetime.now(UTC),
            )
        )

    await db.commit()
    await db.refresh(invitation)

    inviter_name = inviter.profile.full_name if inviter.profile else inviter.email
    await send_team_invitation_email(email, inviter_name, organization.name, token)
    return invitation


async def list_pending_invitations(db: AsyncSession, organization_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(TeamInvitation)
        .where(TeamInvitation.organization_id == organization_id, TeamInvitation.status == "pending")
        .order_by(TeamInvitation.created_at.desc())
    )
    invitations = (await db.execute(stmt)).scalars().all()

    results = []
    for inv in invitations:
        role = await db.get(Role, inv.role_id)
        inviter = await db.get(User, inv.invited_by_id) if inv.invited_by_id else None
        results.append(
            {
                "id": inv.id,
                "email": inv.email,
                "role": role.name.value if role else "member",
                "invited_by": inviter.email if inviter else None,
                "status": inv.status,
                "created_at": inv.created_at,
                "expires_at": inv.expires_at,
            }
        )
    return results


async def resend_invitation(db: AsyncSession, invitation_id: uuid.UUID, organization: Organization, inviter: User) -> None:
    invitation = await db.get(TeamInvitation, invitation_id)
    if invitation is None or invitation.organization_id != organization.id:
        raise NotFoundError("Invitation not found")

    token = generate_token(24)
    invitation.token_hash = hash_password(token)
    invitation.expires_at = datetime.now(UTC) + timedelta(days=INVITATION_EXPIRE_DAYS)
    await db.commit()

    inviter_name = inviter.profile.full_name if inviter.profile else inviter.email
    await send_team_invitation_email(invitation.email, inviter_name, organization.name, token)


async def cancel_invitation(db: AsyncSession, invitation_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    invitation = await db.get(TeamInvitation, invitation_id)
    if invitation is None or invitation.organization_id != organization_id:
        raise NotFoundError("Invitation not found")
    invitation.status = "cancelled"
    await db.commit()


async def accept_invitation(db: AsyncSession, token: str) -> TeamInvitation:
    stmt = select(TeamInvitation).where(TeamInvitation.status == "pending")
    candidates = (await db.execute(stmt)).scalars().all()

    invitation = next((inv for inv in candidates if verify_password(token, inv.token_hash)), None)
    if invitation is None:
        raise BadRequestError("Invalid or expired invitation")
    if invitation.expires_at < datetime.now(UTC):
        raise BadRequestError("This invitation has expired")

    user_stmt = select(User).where(User.email == invitation.email)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if user is None:
        raise BadRequestError("Please create an account with this email first, then accept the invitation")

    member_stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == invitation.organization_id,
        OrganizationMember.user_id == user.id,
    )
    member = (await db.execute(member_stmt)).scalar_one_or_none()
    if member:
        member.status = MemberStatus.ACTIVE
        member.joined_at = datetime.now(UTC)
    else:
        db.add(
            OrganizationMember(
                organization_id=invitation.organization_id,
                user_id=user.id,
                role_id=invitation.role_id,
                status=MemberStatus.ACTIVE,
                joined_at=datetime.now(UTC),
            )
        )

    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(UTC)
    await db.commit()
    return invitation


async def _get_membership(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID) -> OrganizationMember:
    stmt = (
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user_id)
        .options(selectinload(OrganizationMember.role))
    )
    member = (await db.execute(stmt)).scalar_one_or_none()
    if member is None:
        raise NotFoundError("Member not found")
    return member


async def _count_owners(db: AsyncSession, organization_id: uuid.UUID) -> int:
    owner_role = await _get_role_by_name(db, "owner")
    stmt = select(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id, OrganizationMember.role_id == owner_role.id
    )
    return len((await db.execute(stmt)).scalars().all())


async def update_member_role(
    db: AsyncSession, organization_id: uuid.UUID, member_user_id: uuid.UUID, new_role_name: str
) -> OrganizationMember:
    member = await _get_membership(db, organization_id, member_user_id)

    if member.role.name == RoleName.OWNER and new_role_name != "owner":
        if await _count_owners(db, organization_id) <= 1:
            raise BadRequestError("Cannot change the role of the workspace's only owner")

    new_role = await _get_role_by_name(db, new_role_name)
    member.role_id = new_role.id
    await db.commit()
    await db.refresh(member, attribute_names=["role"])
    return member


async def remove_member(db: AsyncSession, organization_id: uuid.UUID, member_user_id: uuid.UUID) -> None:
    member = await _get_membership(db, organization_id, member_user_id)

    if member.role.name == RoleName.OWNER and await _count_owners(db, organization_id) <= 1:
        raise BadRequestError("Cannot remove the workspace's only owner")

    await db.delete(member)
    await db.commit()


async def list_role_permissions(db: AsyncSession) -> list[dict]:
    """The role -> permission-code matrix, straight from the database.

    `scripts/seed_data.py` seeds it and `api.deps.require_permission` enforces
    it; exposing it read-only lets the Team page render the same matrix the API
    actually applies instead of a copy that can silently drift.

    `superadmin` is filtered out: it is a platform-operator flag, not a
    workspace role a customer can assign.
    """
    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.name != RoleName.SUPERADMIN)
    )
    roles = (await db.execute(stmt)).scalars().all()

    order = [RoleName.OWNER, RoleName.ADMIN, RoleName.MEMBER, RoleName.VIEWER]
    roles = sorted(roles, key=lambda r: order.index(r.name) if r.name in order else len(order))

    return [
        {
            "role": role.name.value,
            "permissions": sorted(permission.code for permission in role.permissions),
        }
        for role in roles
    ]


async def list_permissions(db: AsyncSession) -> list[dict]:
    """Every seeded capability, with its human-readable description."""
    stmt = select(Permission).order_by(Permission.code)
    permissions = (await db.execute(stmt)).scalars().all()
    return [{"code": p.code, "description": p.description} for p in permissions]
