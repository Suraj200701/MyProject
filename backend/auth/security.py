"""Password hashing and OTP generation primitives."""

import secrets
import string

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_otp(length: int = 6) -> str:
    """Cryptographically-random numeric OTP."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_token(length: int = 32) -> str:
    """URL-safe random token for email verification / password reset links."""
    return secrets.token_urlsafe(length)
