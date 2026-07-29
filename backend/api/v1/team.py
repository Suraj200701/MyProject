"""Team membership and invitation endpoints."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_membership, get_current_organization, get_current_user, require_org_role
from database.session import get_db
from models.enums import RoleName
from models.organization import Organization, OrganizationMember
from models.user import User
from schemas.common import MessageResponse
from schemas.team import AcceptInvitationRequest, InvitationOut, InviteMemberRequest, MemberOut, UpdateMemberRoleRequest
from services import team_service

router = APIRouter(prefix="/team", tags=["Team"])


@router.get("/members", response_model=list[MemberOut])
async def list_members(
    organization: Organization = Depends(get_current_organization),
    _membership: OrganizationMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    return await team_service.list_members(db, organization.id)


@router.post("/invite", response_model=InvitationOut, status_code=201)
async def invite_member(
    payload: InviteMemberRequest,
    organization: Organization = Depends(get_current_organization),
    _membership: OrganizationMember = Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN)),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    invitation = await team_service.invite_member(db, organization, user, payload.email, payload.role)
    return await _invitation_out(db, invitation)


async def _invitation_out(db: AsyncSession, invitation) -> InvitationOut:
    from models.user import Role, User as UserModel

    role = await db.get(Role, invitation.role_id)
    inviter = await db.get(UserModel, invitation.invited_by_id) if invitation.invited_by_id else None
    return InvitationOut(
        id=invitation.id,
        email=invitation.email,
        role=role.name.value if role else "member",
        invited_by=inviter.email if inviter else None,
        status=invitation.status,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
    )


@router.get("/invitations", response_model=list[InvitationOut])
async def list_invitations(
    organization: Organization = Depends(get_current_organization),
    _membership: OrganizationMember = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
):
    rows = await team_service.list_pending_invitations(db, organization.id)
    return [InvitationOut(**row) for row in rows]


@router.post("/invitations/{invitation_id}/resend", response_model=MessageResponse)
async def resend_invitation(
    invitation_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    _membership: OrganizationMember = Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN)),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await team_service.resend_invitation(db, invitation_id, organization, user)
    return MessageResponse(message="Invitation resent")


@router.delete("/invitations/{invitation_id}", response_model=MessageResponse)
async def cancel_invitation(
    invitation_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    _membership: OrganizationMember = Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await team_service.cancel_invitation(db, invitation_id, organization.id)
    return MessageResponse(message="Invitation cancelled")


@router.patch("/members/{member_user_id}/role", response_model=MessageResponse)
async def update_member_role(
    member_user_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    organization: Organization = Depends(get_current_organization),
    _membership: OrganizationMember = Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await team_service.update_member_role(db, organization.id, member_user_id, payload.role)
    return MessageResponse(message="Role updated")


@router.delete("/members/{member_user_id}", response_model=MessageResponse)
async def remove_member(
    member_user_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    _membership: OrganizationMember = Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    await team_service.remove_member(db, organization.id, member_user_id)
    return MessageResponse(message="Member removed")


@router.post("/invitations/accept", response_model=MessageResponse)
async def accept_invitation(payload: AcceptInvitationRequest, db: AsyncSession = Depends(get_db)):
    await team_service.accept_invitation(db, payload.token)
    return MessageResponse(message="Invitation accepted")
