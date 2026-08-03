"""Import every model module so `Base.metadata` is fully populated —
required for Alembic autogenerate and for cross-file relationship() string
resolution to succeed."""

from database.base import Base
from models.billing import (
    CreditWallet,
    Invoice,
    Payment,
    Subscription,
    SubscriptionPlan,
    Transaction,
    WebhookEvent,
)
from models.document import Document
from models.lead import Company, Lead, LeadActivity, LeadNote
from models.lead_import import LeadImport
from models.notification import Notification, NotificationPreference, PushSubscription
from models.organization import Organization, OrganizationMember, TeamInvitation
from models.otp import AuthTokenLog, OtpRequest
from models.search import ApiProvider, Export, Search, SearchProviderRun, WebsiteScan
from models.settings import ApiKey, BackupSnapshot, Setting
from models.user import (
    ActivityLog,
    OAuthAccount,
    Permission,
    Role,
    RolePermission,
    User,
    UserProfile,
    UserSession,
)

__all__ = [
    "Base",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "UserProfile",
    "OAuthAccount",
    "UserSession",
    "ActivityLog",
    "Organization",
    "OrganizationMember",
    "TeamInvitation",
    "Company",
    "Lead",
    "LeadImport",
    "LeadNote",
    "LeadActivity",
    "ApiProvider",
    "Search",
    "SearchProviderRun",
    "WebsiteScan",
    "Export",
    "SubscriptionPlan",
    "Subscription",
    "CreditWallet",
    "Payment",
    "Transaction",
    "Invoice",
    "WebhookEvent",
    "Notification",
    "NotificationPreference",
    "PushSubscription",
    "ApiKey",
    "Setting",
    "BackupSnapshot",
    "Document",
    "OtpRequest",
    "AuthTokenLog",
]
