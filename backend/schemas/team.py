"""Pydantic schemas for team membership and invitations."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

InviteRole = Literal["admin", "member", "viewer"]


class MemberOut(BaseModel):
    id: uuid.UUID  # OrganizationMember.id
    user_id: uuid.UUID
    name: str | None = None
    email: EmailStr
    avatar_url: str | None = None
    role: str
    status: str
    joined_at: datetime | None = None
    last_active: datetime | None = None


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: InviteRole = "member"


class InvitationOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str
    invited_by: str | None = None
    status: str
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class UpdateMemberRoleRequest(BaseModel):
    role: InviteRole


class AcceptInvitationRequest(BaseModel):
    token: str
