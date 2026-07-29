"""Business logic for profile, organization, API key, generic settings,
and backup-snapshot management."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import generate_token, hash_password
from models.enums import SettingScope
from models.lead import Company, Lead
from models.organization import Organization
from models.search import Search
from models.settings import ApiKey, BackupSnapshot, Setting
from models.user import User, UserProfile
from schemas.settings import OrganizationUpdate, ProfileOut, ProfileUpdate
from utils.exceptions import NotFoundError


async def get_profile(db: AsyncSession, user: User) -> ProfileOut:
    profile = user.profile
    return ProfileOut(
        id=user.id,
        email=user.email,
        phone=user.phone,
        full_name=profile.full_name if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        job_title=profile.job_title if profile else None,
        timezone=profile.timezone if profile else "UTC",
        locale=profile.locale if profile else "en-US",
    )


async def update_profile(db: AsyncSession, user: User, data: ProfileUpdate) -> ProfileOut:
    profile = user.profile
    if profile is None:
        profile = UserProfile(user_id=user.id, timezone="UTC", locale="en-US")
        db.add(profile)

    updates = data.model_dump(exclude_unset=True)
    if "phone" in updates:
        user.phone = updates.pop("phone")
    for field, value in updates.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(user, attribute_names=["profile"])
    return await get_profile(db, user)


async def update_organization(db: AsyncSession, organization: Organization, data: OrganizationUpdate) -> Organization:
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(organization, field, value)
    await db.commit()
    await db.refresh(organization)
    return organization


def _mask_key(prefix: str) -> str:
    return f"{prefix}{'•' * 12}"


async def generate_api_key(db: AsyncSession, organization_id: uuid.UUID, user_id: uuid.UUID, name: str) -> tuple[ApiKey, str]:
    full_key = f"lm_live_{generate_token(24)}"
    prefix = full_key[:12]

    api_key = ApiKey(
        organization_id=organization_id,
        user_id=user_id,
        name=name,
        key_prefix=prefix,
        key_hash=hash_password(full_key),
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, full_key


async def list_api_keys(db: AsyncSession, organization_id: uuid.UUID) -> list[ApiKey]:
    stmt = (
        select(ApiKey)
        .where(ApiKey.organization_id == organization_id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def revoke_api_key(db: AsyncSession, key_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    key = await db.get(ApiKey, key_id)
    if key is None or key.organization_id != organization_id:
        raise NotFoundError("API key not found")
    key.revoked_at = datetime.now(UTC)
    await db.commit()


async def get_setting(db: AsyncSession, scope: SettingScope, scope_id: uuid.UUID | None, key: str, default: dict | None = None) -> dict | None:
    stmt = select(Setting).where(Setting.scope == scope, Setting.scope_id == scope_id, Setting.key == key)
    row = (await db.execute(stmt)).scalar_one_or_none()
    return row.value if row else default


async def set_setting(db: AsyncSession, scope: SettingScope, scope_id: uuid.UUID | None, key: str, value: dict) -> Setting:
    stmt = select(Setting).where(Setting.scope == scope, Setting.scope_id == scope_id, Setting.key == key)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row:
        row.value = value
    else:
        row = Setting(scope=scope, scope_id=scope_id, key=key, value=value)
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def create_backup_snapshot(db: AsyncSession, organization_id: uuid.UUID, label: str | None) -> BackupSnapshot:
    counts = {}
    for model in (Lead, Company, Search):
        stmt = select(func.count()).select_from(model).where(model.organization_id == organization_id)
        counts[model.__tablename__] = (await db.execute(stmt)).scalar_one()

    # Rough size estimate (bytes) — proportional to row counts across the
    # org's core tables. This is a metadata record of a backup, not a real
    # export/restore engine.
    estimated_size = sum(counts.values()) * 850 + 50_000

    snapshot = BackupSnapshot(
        organization_id=organization_id,
        label=label or f"Manual backup {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}",
        size_bytes=estimated_size,
        status="completed",
        created_at=datetime.now(UTC),
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def list_backup_snapshots(db: AsyncSession, organization_id: uuid.UUID) -> list[BackupSnapshot]:
    stmt = (
        select(BackupSnapshot)
        .where(BackupSnapshot.organization_id == organization_id)
        .order_by(BackupSnapshot.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())
