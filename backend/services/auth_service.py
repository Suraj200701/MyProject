"""Business logic for signup, login, token refresh, password reset, email
verification, and OTP-based login."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.jwt import (
    TokenError,
    TokenType,
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
)
from auth.otp_service import issue_otp, verify_otp
from auth.security import generate_token, hash_password, verify_password
from config.settings import settings
from models.billing import CreditWallet, Subscription, SubscriptionPlan
from models.enums import MemberStatus, OtpPurpose, RoleName, SubscriptionStatus
from models.organization import Organization, OrganizationMember
from models.otp import AuthTokenLog
from models.user import Role, User, UserProfile, UserSession
from notifications.email_service import send_otp_email, send_password_reset_email, send_verification_email
from repositories.user_repository import UserRepository
from schemas.user import LoginRequest, SignupRequest, TokenResponse
from utils.exceptions import BadRequestError, ConflictError, UnauthorizedError

logger = logging.getLogger("leadmaster.auth")


async def _get_role(db: AsyncSession, name: RoleName) -> Role:
    role = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
    if role is None:
        raise RuntimeError(f"Role '{name}' is not seeded. Run: python -m scripts.seed_data")
    return role


async def _issue_session(
    db: AsyncSession, user: User, request: Request | None, remember_me: bool = False
) -> TokenResponse:
    access_token = create_access_token(str(user.id), user.role.name.value if user.role else RoleName.MEMBER.value)
    refresh_token = create_refresh_token(str(user.id))

    days = settings.REFRESH_TOKEN_EXPIRE_DAYS if remember_me else 7
    ip = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None

    session_row = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_password(refresh_token),
        ip_address=ip,
        user_agent=user_agent,
        last_active_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=days),
    )
    db.add(session_row)

    user.last_login_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user, attribute_names=["role", "profile"])

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)


async def signup(db: AsyncSession, data: SignupRequest, request: Request | None = None) -> TokenResponse:
    repo = UserRepository(db)
    if await repo.email_exists(data.email):
        raise ConflictError("An account with this email already exists")

    owner_role = await _get_role(db, RoleName.OWNER)
    free_plan = (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "Free"))
    ).scalar_one_or_none()

    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        role_id=owner_role.id,
        is_active=True,
        is_email_verified=False,
    )
    db.add(user)
    await db.flush()

    db.add(UserProfile(user_id=user.id, full_name=data.full_name))

    organization = Organization(name=data.company_name, owner_id=user.id)
    db.add(organization)
    await db.flush()

    db.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role_id=owner_role.id,
            status=MemberStatus.ACTIVE,
            joined_at=datetime.now(UTC),
        )
    )
    db.add(CreditWallet(organization_id=organization.id, balance=free_plan.credits_included if free_plan else 9999999))
    if free_plan:
        db.add(
            Subscription(
                organization_id=organization.id,
                plan_id=free_plan.id,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=datetime.now(UTC),
                current_period_end=datetime.now(UTC) + timedelta(days=30),
            )
        )

    await db.flush()

    verification_token = create_email_verification_token(str(user.id))
    payload = decode_token(verification_token, TokenType.EMAIL_VERIFICATION)
    db.add(
        AuthTokenLog(
            user_id=user.id,
            jti=payload["jti"],
            token_type=TokenType.EMAIL_VERIFICATION.value,
            created_at=datetime.now(UTC),
        )
    )

    tokens = await _issue_session(db, user, request)

    # A delivery failure must not fail the signup. By this point the user, org,
    # membership, wallet, subscription and session are all committed, so raising
    # here returns a 500 while a real account stays behind — and the retry then
    # hits "An account with this email already exists", which tells the user the
    # opposite of what happened. Verification can be re-requested from Settings
    # (POST /auth/resend-verification), so a logged failure costs far less than
    # a signup the user believes was rejected.
    try:
        await send_verification_email(user.email, verification_token)
    except Exception:
        logger.exception("Verification email to %s failed; signup kept.", user.email)

    return tokens


async def login(db: AsyncSession, data: LoginRequest, request: Request | None = None) -> TokenResponse:
    repo = UserRepository(db)
    user = await repo.get_by_email(data.email)

    if user is None or user.hashed_password is None or not verify_password(data.password, user.hashed_password):
        raise UnauthorizedError("Incorrect email or password")

    if not user.is_active:
        raise UnauthorizedError("This account has been deactivated")

    return await _issue_session(db, user, request, remember_me=data.remember_me)


async def refresh_session(db: AsyncSession, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token, TokenType.REFRESH)
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user_id = uuid.UUID(payload["sub"])
    stmt = select(User).where(User.id == user_id).options(selectinload(User.role), selectinload(User.profile))
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    access_token = create_access_token(str(user.id), user.role.name.value if user.role else RoleName.MEMBER.value)
    new_refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token, user=user)


async def logout(db: AsyncSession, user: User) -> None:
    """Revokes all active sessions for this user (simple, safe default —
    a targeted single-session revoke is exposed via DELETE /auth/sessions/{id})."""
    stmt = select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
    sessions = (await db.execute(stmt)).scalars().all()
    for s in sessions:
        s.revoked_at = datetime.now(UTC)
    await db.commit()


async def request_password_reset(db: AsyncSession, email: str) -> None:
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if user is None:
        return  # do not reveal account existence

    token = create_password_reset_token(str(user.id))
    payload = decode_token(token, TokenType.PASSWORD_RESET)
    db.add(
        AuthTokenLog(
            user_id=user.id, jti=payload["jti"], token_type=TokenType.PASSWORD_RESET.value, created_at=datetime.now(UTC)
        )
    )
    await db.commit()

    # Non-fatal for the same reason as signup, plus a privacy one. This endpoint
    # answers 200 for every address precisely so it cannot be used to test which
    # emails are registered — but only a *real* user reaches this line, so an
    # escaping delivery error turns a 500 into exactly that oracle: 500 means the
    # account exists, 200 means it doesn't.
    try:
        await send_password_reset_email(user.email, token)
    except Exception:
        logger.exception("Password reset email to %s failed.", user.email)


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    try:
        payload = decode_token(token, TokenType.PASSWORD_RESET)
    except TokenError as exc:
        raise BadRequestError(str(exc)) from exc

    log_stmt = select(AuthTokenLog).where(AuthTokenLog.jti == payload["jti"])
    log = (await db.execute(log_stmt)).scalar_one_or_none()
    if log is None or log.consumed_at is not None:
        raise BadRequestError("This reset link has already been used or is invalid")

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise BadRequestError("Invalid reset link")

    user.hashed_password = hash_password(new_password)
    log.consumed_at = datetime.now(UTC)
    await db.commit()


async def verify_email(db: AsyncSession, token: str) -> None:
    try:
        payload = decode_token(token, TokenType.EMAIL_VERIFICATION)
    except TokenError as exc:
        raise BadRequestError(str(exc)) from exc

    log_stmt = select(AuthTokenLog).where(AuthTokenLog.jti == payload["jti"])
    log = (await db.execute(log_stmt)).scalar_one_or_none()
    if log is None or log.consumed_at is not None:
        raise BadRequestError("This verification link has already been used or is invalid")

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise BadRequestError("Invalid verification link")

    user.is_email_verified = True
    log.consumed_at = datetime.now(UTC)
    await db.commit()


async def request_login_otp(db: AsyncSession, redis: Redis, email: str) -> None:
    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if user is None:
        return  # do not reveal account existence

    code = await issue_otp(redis, email, OtpPurpose.LOGIN.value)
    await send_otp_email(email, code, OtpPurpose.LOGIN.value)


async def verify_login_otp(db: AsyncSession, redis: Redis, email: str, code: str, request: Request | None = None) -> TokenResponse:
    ok = await verify_otp(redis, email, OtpPurpose.LOGIN.value, code)
    if not ok:
        raise UnauthorizedError("Incorrect or expired code")

    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if user is None:
        raise UnauthorizedError("Account not found")

    return await _issue_session(db, user, request)
