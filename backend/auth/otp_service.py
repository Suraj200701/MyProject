"""Redis-backed OTP issue/verify with attempt-limiting."""

from redis.asyncio import Redis

from auth.security import generate_otp
from config.settings import settings
from utils.exceptions import BadRequestError, TooManyRequestsError

MAX_VERIFY_ATTEMPTS = 5


def _otp_key(destination: str, purpose: str) -> str:
    return f"otp:{purpose}:{destination.lower()}"


def _attempts_key(destination: str, purpose: str) -> str:
    return f"otp_attempts:{purpose}:{destination.lower()}"


def _rate_key(destination: str, purpose: str) -> str:
    return f"otp_rate:{purpose}:{destination.lower()}"


async def issue_otp(redis: Redis, destination: str, purpose: str) -> str:
    rate_key = _rate_key(destination, purpose)
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, 3600)
    if count > settings.OTP_RATE_LIMIT_PER_HOUR:
        raise TooManyRequestsError("Too many OTP requests. Please try again later.")

    code = generate_otp(settings.OTP_LENGTH)
    await redis.set(_otp_key(destination, purpose), code, ex=settings.OTP_EXPIRE_SECONDS)
    await redis.delete(_attempts_key(destination, purpose))
    return code


async def verify_otp(redis: Redis, destination: str, purpose: str, code: str) -> bool:
    key = _otp_key(destination, purpose)
    attempts_key = _attempts_key(destination, purpose)

    attempts = await redis.incr(attempts_key)
    if attempts == 1:
        await redis.expire(attempts_key, settings.OTP_EXPIRE_SECONDS)
    if attempts > MAX_VERIFY_ATTEMPTS:
        await redis.delete(key)
        raise TooManyRequestsError("Too many incorrect attempts. Request a new code.")

    stored = await redis.get(key)
    if stored is None:
        raise BadRequestError("Code has expired. Please request a new one.")

    if stored != code:
        return False

    await redis.delete(key)
    await redis.delete(attempts_key)
    return True
