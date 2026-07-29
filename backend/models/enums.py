"""Shared enum types used across models (kept in one place to avoid
circular imports and to give Alembic stable, named Postgres ENUM types)."""

import enum


class RoleName(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    SUPERADMIN = "superadmin"  # platform-level admin, not tied to one org


class MemberStatus(str, enum.Enum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"


class OAuthProvider(str, enum.Enum):
    GOOGLE = "google"


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    LOST = "lost"


class ProviderCategory(str, enum.Enum):
    SEARCH = "Search"
    MAPS = "Maps"
    BUSINESS = "Business"
    CRM = "CRM"
    AI = "AI"


class ProviderStatus(str, enum.Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class SearchStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportFormat(str, enum.Enum):
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    JSON = "json"


class ExportStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    EXPIRED = "expired"
    FAILED = "failed"


class BillingInterval(str, enum.Enum):
    MONTH = "month"
    YEAR = "year"


class SubscriptionStatus(str, enum.Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class TransactionType(str, enum.Enum):
    SUBSCRIPTION_CHARGE = "subscription_charge"
    CREDIT_TOPUP = "credit_topup"
    CREDIT_USAGE = "credit_usage"
    REFUND = "refund"


class InvoiceStatus(str, enum.Enum):
    PAID = "paid"
    PENDING = "pending"
    FAILED = "failed"


class NotificationType(str, enum.Enum):
    SEARCH = "search"
    EXPORT = "export"
    API = "api"
    RECOMMENDATION = "recommendation"
    SYSTEM = "system"


class OtpPurpose(str, enum.Enum):
    LOGIN = "login"
    VERIFY_EMAIL = "verify_email"
    VERIFY_PHONE = "verify_phone"
    RESET_PASSWORD = "reset_password"


class SettingScope(str, enum.Enum):
    USER = "user"
    ORGANIZATION = "organization"
    GLOBAL = "global"
