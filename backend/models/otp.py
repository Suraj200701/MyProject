"""OTP and stateless-token audit tables.

The live OTP *value* and its TTL live in Redis (fast expiry, auto-cleanup —
see auth/otp_service.py). This table is the durable audit trail: who
requested an OTP, for what purpose, when, and whether it was consumed —
needed for abuse detection and the rate-limit window.

Email verification / password reset links are signed JWTs (auth/jwt.py) so
they need no DB row to be *verified*, but we log the token's `jti` here so
a token can only ever be consumed once even before it expires.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base, UUIDPrimaryKeyMixin
from models.enums import OtpPurpose


class OtpRequest(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "otp_requests"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    destination: Mapped[str] = mapped_column(String(255), nullable=False, index=True)  # email or phone
    purpose: Mapped[OtpPurpose] = mapped_column(nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class AuthTokenLog(Base, UUIDPrimaryKeyMixin):
    """Single-use enforcement for email-verification / password-reset JWTs."""

    __tablename__ = "auth_token_log"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    token_type: Mapped[str] = mapped_column(String(30), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
