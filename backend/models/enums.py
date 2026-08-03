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
    # A provider that never ran — no credentials, or not applicable to the
    # query. Distinct from FAILED: nothing went wrong, so surfacing it as a
    # failure made every search look like six broken integrations.
    SKIPPED = "skipped"


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


class ExportResource(str, enum.Enum):
    """What an export contains.

    Stored on the row because the history list and the download endpoint both
    need to know what a file holds without re-deriving it from the filename.
    """

    LEADS = "leads"
    SEARCH_RESULTS = "search_results"
    DASHBOARD_REPORT = "dashboard_report"
    ANALYTICS_REPORT = "analytics_report"


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


class ImportSource(str, enum.Enum):
    """Where an import's rows came from.

    Recorded because the workflow differs: a Google Maps Extractor file arrives
    with a keyword/location the user searched for, and the history view shows
    that context so a run can be recognised weeks later.
    """

    CSV_UPLOAD = "csv_upload"
    GOOGLE_MAPS_EXTRACTOR = "google_maps_extractor"


class ImportStatus(str, enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    # Parsed, but every row was rejected or duplicated — worth distinguishing
    # from success so the user investigates their file instead of their filters.
    COMPLETED_EMPTY = "completed_empty"
    FAILED = "failed"
