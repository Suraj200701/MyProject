"""Domain-level exceptions mapped to HTTP responses by api/deps.py handlers."""

from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "You do not have permission to perform this action"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class BadRequestError(HTTPException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class TooManyRequestsError(HTTPException):
    def __init__(self, detail: str = "Too many requests"):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


class InsufficientCreditsError(HTTPException):
    """402 — the organization's credit balance cannot cover the operation.

    Distinct from 403 (permission) and 429 (rate limit): the caller is
    authorized and within rate limits, but needs to top up. The response
    carries the shortfall so the frontend can prompt for the right amount.
    """

    def __init__(self, required: int, available: int):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Insufficient credits: this operation requires {required} credit(s) "
                f"but only {available} remain. Top up to continue."
            ),
        )
        self.required = required
        self.available = available


class UnsafeUrlError(HTTPException):
    """400 — a user-supplied URL failed the SSRF/validation guard.

    The message deliberately states the category of problem without echoing
    resolved internal IPs back to the caller, so the endpoint can't be used
    to map internal network topology.
    """

    def __init__(self, reason: str = "This URL cannot be scanned"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)
