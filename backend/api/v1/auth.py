"""Authentication endpoints: signup, login, refresh, logout, password
reset, email verification, OTP login, Google OAuth, and session
management."""

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from auth.google_oauth import build_authorization_url, exchange_code_for_tokens, fetch_userinfo
from auth.jwt import create_access_token
from auth.security import hash_password, verify_password
from config.settings import settings
from database.session import get_db
from models.enums import MemberStatus, RoleName, SubscriptionStatus
from models.billing import CreditWallet, Subscription, SubscriptionPlan
from models.organization import Organization, OrganizationMember
from models.user import OAuthAccount, Role, User, UserProfile, UserSession
from redis_cache.client import get_redis
from schemas.common import MessageResponse
from schemas.user import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    OtpRequestSchema,
    OtpVerifyRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SessionOut,
    SignupRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)
from services import auth_service
from utils.exceptions import BadRequestError, UnauthorizedError

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(payload: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    return await auth_service.signup(db, payload, request)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, payload, request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.refresh_session(db, payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, user)
    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.hashed_password is None or not verify_password(payload.current_password, user.hashed_password):
        raise UnauthorizedError("Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    await db.commit()
    return MessageResponse(message="Password updated successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.request_password_reset(db, payload.email)
    return MessageResponse(message="If that email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_password(db, payload.token, payload.new_password)
    return MessageResponse(message="Password reset successfully")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.verify_email(db, payload.token)
    return MessageResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from auth.jwt import TokenType, create_email_verification_token, decode_token
    from models.otp import AuthTokenLog
    from notifications.email_service import send_verification_email

    if user.is_email_verified:
        return MessageResponse(message="Email is already verified")

    token = create_email_verification_token(str(user.id))
    payload = decode_token(token, TokenType.EMAIL_VERIFICATION)
    db.add(
        AuthTokenLog(
            user_id=user.id, jti=payload["jti"], token_type=TokenType.EMAIL_VERIFICATION.value, created_at=datetime.now(UTC)
        )
    )
    await db.commit()
    await send_verification_email(user.email, token)
    return MessageResponse(message="Verification email sent")


@router.post("/otp/request", response_model=MessageResponse)
async def request_otp(payload: OtpRequestSchema, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    await auth_service.request_login_otp(db, redis, payload.email)
    return MessageResponse(message="If that email exists, a verification code has been sent")


@router.post("/otp/verify", response_model=TokenResponse)
async def verify_otp_endpoint(
    payload: OtpVerifyRequest, request: Request, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)
):
    return await auth_service.verify_login_otp(db, redis, payload.email, payload.code, request)


# --- Sessions (Settings > Security > Active Sessions) ---


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .order_by(UserSession.last_active_at.desc())
    )
    sessions = (await db.execute(stmt)).scalars().all()
    return [SessionOut.model_validate(s) for s in sessions]


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session_row = await db.get(UserSession, session_id)
    if session_row is None or session_row.user_id != user.id:
        raise BadRequestError("Session not found")
    session_row.revoked_at = datetime.now(UTC)
    await db.commit()
    return MessageResponse(message="Session revoked")


# --- Google OAuth ---


@router.get("/google/login")
async def google_login(redis: Redis = Depends(get_redis)):
    state = secrets.token_urlsafe(24)
    await redis.set(f"oauth_state:{state}", "1", ex=600)
    return RedirectResponse(build_authorization_url(state))


@router.get("/google/callback")
async def google_callback(
    code: str, state: str, request: Request, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)
):
    valid = await redis.get(f"oauth_state:{state}")
    if not valid:
        raise BadRequestError("Invalid or expired OAuth state")
    await redis.delete(f"oauth_state:{state}")

    tokens = await exchange_code_for_tokens(code)
    profile = await fetch_userinfo(tokens["access_token"])

    stmt = select(OAuthAccount).where(
        OAuthAccount.provider == "google", OAuthAccount.provider_account_id == profile["sub"]
    )
    oauth_account = (await db.execute(stmt)).scalar_one_or_none()

    if oauth_account:
        user = await db.get(User, oauth_account.user_id)
    else:
        from repositories.user_repository import UserRepository

        repo = UserRepository(db)
        user = await repo.get_by_email(profile["email"])

        if user is None:
            owner_role = (await db.execute(select(Role).where(Role.name == RoleName.OWNER))).scalar_one()
            free_plan = (
                await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "Free"))
            ).scalar_one_or_none()

            user = User(
                email=profile["email"].lower(),
                hashed_password=None,
                role_id=owner_role.id,
                is_active=True,
                is_email_verified=bool(profile.get("email_verified")),
            )
            db.add(user)
            await db.flush()
            db.add(UserProfile(user_id=user.id, full_name=profile.get("name"), avatar_url=profile.get("picture")))

            organization = Organization(name=f"{profile.get('name', 'My')}'s Workspace", owner_id=user.id)
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
            db.add(CreditWallet(organization_id=organization.id, balance=free_plan.credits_included if free_plan else 100))
            if free_plan:
                db.add(Subscription(organization_id=organization.id, plan_id=free_plan.id, status=SubscriptionStatus.ACTIVE))

        db.add(
            OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_account_id=profile["sub"],
                access_token=tokens.get("access_token"),
                refresh_token=tokens.get("refresh_token"),
            )
        )

    user.last_login_at = datetime.now(UTC)
    await db.commit()

    access_token = create_access_token(str(user.id), RoleName.OWNER.value)
    return RedirectResponse(f"{settings.FRONTEND_URL}/dashboard?access_token={access_token}")
