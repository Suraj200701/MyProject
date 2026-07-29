"""Profile, organization, API key, generic settings, and backup endpoints."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_membership, get_current_organization, get_current_user, require_org_role
from database.session import get_db
from models.enums import RoleName, SettingScope
from models.organization import Organization, OrganizationMember
from models.user import User
from schemas.common import MessageResponse
from schemas.settings import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyOut,
    BackupSnapshotCreate,
    BackupSnapshotOut,
    OrganizationOut,
    OrganizationUpdate,
    ProfileOut,
    ProfileUpdate,
    SettingOut,
    SettingUpdate,
)
from services import settings_service
from utils.exceptions import BadRequestError

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/profile", response_model=ProfileOut)
async def get_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await settings_service.get_profile(db, user)


@router.patch("/profile", response_model=ProfileOut)
async def update_profile(
    payload: ProfileUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await settings_service.update_profile(db, user, payload)


@router.get("/organization", response_model=OrganizationOut)
async def get_organization(organization: Organization = Depends(get_current_organization)):
    return organization


@router.patch("/organization", response_model=OrganizationOut)
async def update_organization(
    payload: OrganizationUpdate,
    organization: Organization = Depends(get_current_organization),
    _membership: OrganizationMember = Depends(require_org_role(RoleName.OWNER, RoleName.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await settings_service.update_organization(db, organization, payload)


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    organization: Organization = Depends(get_current_organization), db: AsyncSession = Depends(get_db)
):
    keys = await settings_service.list_api_keys(db, organization.id)
    return [
        ApiKeyOut(id=k.id, name=k.name, key_prefix=k.key_prefix, masked=f"{k.key_prefix}{'•' * 12}", last_used_at=k.last_used_at, created_at=k.created_at)
        for k in keys
    ]


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    payload: ApiKeyCreate,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    api_key, full_key = await settings_service.generate_api_key(db, organization.id, user.id, payload.name)
    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        masked=f"{api_key.key_prefix}{'•' * 12}",
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        key=full_key,
    )


@router.delete("/api-keys/{key_id}", response_model=MessageResponse)
async def revoke_api_key(
    key_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    await settings_service.revoke_api_key(db, key_id, organization.id)
    return MessageResponse(message="API key revoked")


@router.get("/backups", response_model=list[BackupSnapshotOut])
async def list_backups(
    organization: Organization = Depends(get_current_organization), db: AsyncSession = Depends(get_db)
):
    return await settings_service.list_backup_snapshots(db, organization.id)


@router.post("/backups", response_model=BackupSnapshotOut, status_code=201)
async def create_backup(
    payload: BackupSnapshotCreate,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    return await settings_service.create_backup_snapshot(db, organization.id, payload.label)


@router.get("/{scope}/{key}", response_model=SettingOut)
async def get_setting(
    scope: str,
    key: str,
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    if scope not in ("user", "organization"):
        raise BadRequestError("scope must be 'user' or 'organization'")
    scope_enum = SettingScope.USER if scope == "user" else SettingScope.ORGANIZATION
    scope_id = user.id if scope == "user" else organization.id

    value = await settings_service.get_setting(db, scope_enum, scope_id, key, default={})
    return SettingOut(scope=scope, key=key, value=value)


@router.put("/{scope}/{key}", response_model=SettingOut)
async def put_setting(
    scope: str,
    key: str,
    payload: SettingUpdate,
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    if scope not in ("user", "organization"):
        raise BadRequestError("scope must be 'user' or 'organization'")
    scope_enum = SettingScope.USER if scope == "user" else SettingScope.ORGANIZATION
    scope_id = user.id if scope == "user" else organization.id

    row = await settings_service.set_setting(db, scope_enum, scope_id, key, payload.value)
    return SettingOut(scope=scope, key=key, value=row.value)
