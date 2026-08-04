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

    # --- Google Maps / Places ---
    # One key serves both the Map module (geocoding) and the Google Places lead
    # provider — enable "Places API (New)" on the same Google Cloud key.
    GOOGLE_MAPS_API_KEY: str = ""

    # --- Mappls (MapmyIndia) — OAuth2 client credentials ---
    MAPPLS_CLIENT_ID: str = ""
    MAPPLS_CLIENT_SECRET: str = ""

    # --- Bing Web Search ---
    # NOTE: standalone Bing Search v7 was retired for new Azure subscriptions in
    # Aug 2025. Usable only with a pre-existing resource; the endpoint is
    # configurable so a compatible gateway can be substituted.
    BING_SEARCH_API_KEY: str = ""
    BING_SEARCH_ENDPOINT: str = "https://api.bing.microsoft.com/v7.0/search"

    # --- Geoapify (OpenStreetMap-derived places + geocoding) ---
    # Single API key, passed as an `apiKey` query parameter.
    GEOAPIFY_API_KEY: str = ""
    # Configurable so a self-hosted or proxied deployment can be substituted.
    #
    # Geoapify splits its API across two version prefixes: Places is `/v2`,
    # geocoding is `/v1` (`/v2/geocode/search` answers 404). So this value is
    # treated as an *origin*: any trailing `/v1` or `/v2` is stripped and the
    # correct version is appended per endpoint. That way the documented
    # `https://api.geoapify.com/v2` works for every call, not just Places.
    GEOAPIFY_BASE_URL: str = "https://api.geoapify.com"
    # Radius of the circle searched around a geocoded location. Geoapify's Places
    # API requires a spatial filter, so a keyword+location search becomes
    # "geocode the location, then search this far around it". 20km covers a
    # metro area without pulling in neighbouring towns.
    GEOAPIFY_SEARCH_RADIUS_METERS: int = 20_000

    @computed_field
    @property
    def geoapify_origin(self) -> str:
        """`GEOAPIFY_BASE_URL` with any trailing version segment removed."""
        origin = (self.GEOAPIFY_BASE_URL or "").rstrip("/")
        for suffix in ("/v1", "/v2"):
            if origin.endswith(suffix):
                return origin[: -len(suffix)]
        return origin

    # --- OpenStreetMap / Overpass (no API key; public community services) ---
    # Nominatim's usage policy REQUIRES an identifying User-Agent and rejects
    # requests without one. It also caps callers at 1 request/second, which
    # `openstreetmap.py` enforces process-wide rather than trusting call sites.
    OSM_USER_AGENT: str = "LeadMasterAI/1.0"
    OVERPASS_URL: str = "https://overpass-api.de/api/interpreter"

    # --- AI lead scoring / summaries ---
    # When unset, scoring falls back to a deterministic signal-based scorer
    # (see services/enrichment/scoring.py) — that fallback is a real heuristic
    # over real lead data, not placeholder output.
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    AI_SCORING_MODEL: str = "gpt-4o-mini"
    AI_SCORING_ENABLED: bool = True
    AI_SCORING_TIMEOUT_SECONDS: float = 20.0
    # Cap leads sent to the LLM per search, bounding token spend per request.
    AI_SCORING_MAX_LEADS_PER_SEARCH: int = 25

    # --- Provider HTTP behaviour ---
    PROVIDER_TIMEOUT_SECONDS: float = 12.0

    # --- Website crawl (Company Website Search + scanner) ---
    SCANNER_ENABLED: bool = True
    # Homepage plus this many minus one likely contact pages.
    WEBSITE_CRAWL_MAX_PAGES: int = 3

    # --- Lead deduplication ---
    DEDUP_ENABLED: bool = True
    # Similarity (0-1) above which two company names in the same city are
    # treated as the same business. 0.88 is deliberately conservative: a false
    # merge silently loses a real lead, which is worse than a duplicate.
    DEDUP_NAME_SIMILARITY_THRESHOLD: float = 0.88

    # --- CSV import ---
    CSV_IMPORT_MAX_ROWS: int = 5000

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
    # Skip metering while ENVIRONMENT == "development".
    #
    # Local work shouldn't be throttled by a 100-credit Free plan, but this is a
    # named flag rather than a bare `if development` so the behaviour is visible
    # in config and can be switched off to exercise the real metering path
    # locally. It cannot affect staging or production: those set
    # ENVIRONMENT to something other than "development", and the check below
    # requires both conditions.
    CREDIT_METERING_DISABLED_IN_DEVELOPMENT: bool = True

    @computed_field
    @property
    def credit_metering_active(self) -> bool:
        """Whether wallet debits actually happen.

        Single source of truth — `usage_service` consults this rather than
        re-deriving the rule, so there is one place to reason about when credits
        are and are not charged.
        """
        if not self.CREDIT_METERING_ENABLED:
            return False
        if self.ENVIRONMENT == "development" and self.CREDIT_METERING_DISABLED_IN_DEVELOPMENT:
            return False
        return True

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

    # --- Export Center ---
    # Hard ceiling on rows in a single export. Bounds memory, file size and how
    # much of the lead database one request can siphon out at once.
    EXPORT_MAX_ROWS: int = 50_000
    # Rejected after rendering if the generated file exceeds this. Separate from
    # MAX_UPLOAD_SIZE_MB: an export is written by us, not uploaded by a client,
    # and a wide 50k-row xlsx is legitimately larger than an upload should be.
    EXPORT_MAX_FILE_SIZE_MB: int = 50
    # At or above this row count the export is handed to Celery and the API
    # responds 202 with status=processing. Below it, the file is generated
    # inline and comes back 201 status=ready — which keeps the common
    # "export this filtered view" case a single request.
    EXPORT_ASYNC_ROW_THRESHOLD: int = 5_000
    # Exports are disposable artifacts, not documents. After this they are
    # marked EXPIRED and their bytes deleted by the cleanup task.
    EXPORT_RETENTION_HOURS: int = 72
    # Per-user budget on export *creation* (the expensive operation). Downloads
    # and history reads are only subject to the global per-IP limiter.
    EXPORT_RATE_LIMIT_PER_HOUR: int = 30
    # Lifetime of a signed download token. Short: it travels in a URL, so it can
    # land in browser history, proxy logs and Referer headers.
    EXPORT_DOWNLOAD_TOKEN_TTL_SECONDS: int = 300

    # --- Frontend ---
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
