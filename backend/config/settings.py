"""
Centralized application configuration.

All values are read from environment variables (see .env.example). Nothing
here is hardcoded to a real secret — production deployments must supply
real values via the environment / a secrets manager.
"""

from functools import lru_cache
from typing import Literal

from pydantic import EmailStr, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "LeadMaster AI API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000"

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # --- Database ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "leadmaster"
    POSTGRES_PASSWORD: str = "leadmaster"
    POSTGRES_DB: str = "leadmaster"

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Sync driver URL, used by Alembic."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    CELERY_BROKER_DB: int = 1
    CELERY_RESULT_DB: int = 2

    @computed_field
    @property
    def CELERY_BROKER_URL(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_BROKER_DB}"

    @computed_field
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.CELERY_RESULT_DB}"

    # --- JWT / Auth ---
    JWT_SECRET_KEY: str = "CHANGE_ME_dev_only_insecure_secret_key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    OTP_EXPIRE_SECONDS: int = 300
    OTP_LENGTH: int = 6

    # --- Google OAuth ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # --- Google Maps ---
    GOOGLE_MAPS_API_KEY: str = ""

    # --- Stripe ---
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # --- Email (SMTP) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_FROM: EmailStr = "noreply@leadmaster.ai"
    EMAIL_FROM_NAME: str = "LeadMaster AI"

    # --- File uploads ---
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp,image/gif"
    ALLOWED_DOCUMENT_TYPES: str = "application/pdf,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"

    @computed_field
    @property
    def allowed_image_types_list(self) -> list[str]:
        return [t.strip() for t in self.ALLOWED_IMAGE_TYPES.split(",") if t.strip()]

    @computed_field
    @property
    def allowed_document_types_list(self) -> list[str]:
        return [t.strip() for t in self.ALLOWED_DOCUMENT_TYPES.split(",") if t.strip()]

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    OTP_RATE_LIMIT_PER_HOUR: int = 5

    # --- Field-level encryption (provider credentials / API keys at rest) ---
    # Fernet key. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Supports rotation: comma-separated, NEWEST FIRST. The first key encrypts;
    # all keys are tried when decrypting, so old ciphertext keeps working.
    PROVIDER_CREDENTIAL_ENCRYPTION_KEY: str = ""

    @computed_field
    @property
    def encryption_keys_list(self) -> list[str]:
        return [k.strip() for k in self.PROVIDER_CREDENTIAL_ENCRYPTION_KEY.split(",") if k.strip()]

    # --- Credit metering ---
    # Charged per result returned by a provider that has no explicit
    # `ApiProvider.credit_cost` set. Provider rows override this.
    DEFAULT_SEARCH_CREDIT_COST_PER_RESULT: int = 1
    # Flat cost of one website scan.
    SCANNER_CREDITS_PER_SCAN: int = 1
    # Hard cap on results sourced from a single provider in one search —
    # bounds both credit spend and (later) third-party API cost.
    #
    # This also sets the ceiling on what a search can reserve, so it has to
    # stay affordable on the smallest plan: with the seeded provider costs
    # (6 credit-units per result across the 5 lead-sourcing providers), a cap
    # of 5 reserves 30 credits, giving the 100-credit Free plan 3 searches.
    # Raising it without raising Free-plan credits would make Free unusable —
    # every search would 402 before it started.
    SEARCH_MAX_RESULTS_PER_PROVIDER: int = 5
    # Master switch. When false, operations run without touching the wallet
    # (matches pre-metering behaviour) — lets metering be rolled out safely.
    CREDIT_METERING_ENABLED: bool = True

    # --- Website scanner: outbound fetch safety (SSRF hardening) ---
    SCANNER_TIMEOUT_SECONDS: float = 15.0
    SCANNER_CONNECT_TIMEOUT_SECONDS: float = 5.0
    SCANNER_MAX_PAGE_BYTES: int = 5 * 1024 * 1024  # 5 MB
    SCANNER_MAX_REDIRECTS: int = 5
    SCANNER_USER_AGENT: str = "LeadMasterBot/1.0 (+https://leadmaster.ai/bot)"
    # Ports the scanner may connect to. Business sites live on 80/443; a
    # permissive list is an SSRF amplifier, so this stays narrow by default.
    SCANNER_ALLOWED_PORTS: str = "80,443"
    # MUST remain false in production. When true, private/loopback targets are
    # permitted — only ever for local development against a test server.
    SCANNER_ALLOW_PRIVATE_NETWORKS: bool = False
    # Extra hostnames/domains to refuse outright, comma-separated.
    SCANNER_BLOCKED_DOMAINS: str = ""

    @computed_field
    @property
    def scanner_allowed_ports_set(self) -> set[int]:
        ports: set[int] = set()
        for chunk in self.SCANNER_ALLOWED_PORTS.split(","):
            chunk = chunk.strip()
            if chunk.isdigit():
                ports.add(int(chunk))
        return ports or {80, 443}

    @computed_field
    @property
    def scanner_blocked_domains_set(self) -> set[str]:
        return {d.strip().lower().lstrip(".") for d in self.SCANNER_BLOCKED_DOMAINS.split(",") if d.strip()}

    # --- Frontend ---
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
