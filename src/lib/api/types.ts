/**
 * TypeScript mirrors of the backend's Pydantic response schemas.
 *
 * These use the API's own **snake_case** field names — they describe the wire
 * format, not what components consume. `src/lib/api/mappers.ts` converts them
 * into the camelCase view types in `src/lib/types.ts`, which is what keeps every
 * existing component's props unchanged.
 *
 * Transcribed from the live OpenAPI schema rather than guessed. Where the
 * backend's naming differs from what you'd expect, there's a note — several of
 * these are easy to get subtly wrong (`UsageOut` reports credits *used*, not
 * remaining; `TransactionOut.credits_delta` is signed).
 */

// --- Envelopes ------------------------------------------------------------

/** Wrapper returned by every paginated list endpoint. */
export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

export interface PageMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

/** Returned by mutations that have nothing else to say. */
export interface MessageResponse {
  success: boolean;
  message: string;
}

/** `DataResponse[int]` — used by GET /notifications/unread-count. */
export interface DataResponse<T> {
  success: boolean;
  data: T;
}

/** Error envelope produced by every backend exception handler. */
export interface ApiErrorBody {
  success: false;
  message: string;
  errors: ValidationErrorDetail[] | null;
}

/** One FastAPI/Pydantic validation failure (only present on 422). */
export interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

// --- Auth ----------------------------------------------------------------

/** Nested on `UserOut`. Separate from the settings-scoped ProfileOut. */
export interface UserProfileOut {
  full_name: string | null;
  avatar_url: string | null;
  job_title: string | null;
  timezone: string;
  locale: string;
}

export interface UserOut {
  id: string;
  email: string;
  phone: string | null;
  is_active: boolean;
  is_email_verified: boolean;
  two_factor_enabled: boolean;
  created_at: string;
  last_login_at: string | null;
  role: string | null;
  /** Name and avatar live here, not on the user root. */
  profile: UserProfileOut | null;
}

/** Response of login, signup, refresh and OTP verify. */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserOut;
}

export interface SessionOut {
  id: string;
  device_label: string | null;
  ip_address: string | null;
  location: string | null;
  last_active_at: string | null;
  created_at: string;
  is_current: boolean;
}

// --- Leads ---------------------------------------------------------------

export type LeadStatusApi = "new" | "contacted" | "qualified" | "converted" | "lost";

export interface LeadOut {
  id: string;
  company: string;
  industry: string | null;
  city: string | null;
  country: string | null;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  rating: number | null;
  revenue_band: string | null;
  lead_score: number;
  status: LeadStatusApi;
  company_type: string | null;
  provider: string | null;
  tags: string[] | null;
  created_at: string;
  gst_number: string | null;
  lat: number | null;
  lng: number | null;
  ai_summary: string | null;
}

export interface LeadNoteOut {
  id: string;
  lead_id: string;
  author_id: string | null;
  text: string;
  created_at: string;
}

export interface LeadActivityOut {
  id: string;
  lead_id: string;
  event_type: string;
  description: string;
  extra_data: Record<string, unknown> | null;
  created_at: string;
}

export interface LeadDetailOut extends LeadOut {
  notes: LeadNoteOut[];
  activities: LeadActivityOut[];
}

export interface LeadCreateBody {
  company: string;
  industry?: string | null;
  company_type?: string | null;
  revenue_band?: string | null;
  website?: string | null;
  gst_number?: string | null;
  city?: string | null;
  country?: string | null;
  lat?: number | null;
  lng?: number | null;
  rating?: number | null;
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  lead_score?: number;
  status?: LeadStatusApi;
  tags?: string[] | null;
  ai_summary?: string | null;
}

/** PATCH /leads/{id} accepts only this subset. */
export interface LeadUpdateBody {
  status?: LeadStatusApi;
  tags?: string[] | null;
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  lead_score?: number;
  ai_summary?: string | null;
}

export interface CsvImportRowError {
  line: number;
  message: string;
  company: string | null;
}

export interface CsvImportResult {
  total_rows: number;
  imported: number;
  duplicates_skipped: number;
  invalid_rows: number;
  errors: CsvImportRowError[];
  dedup_signals: Record<string, number>;
}

// --- Search / providers / scans -----------------------------------------

/**
 * Backend enum has no "pending" member. `skipped` means a provider never ran
 * (no credentials, or not applicable) — it is not a failure.
 */
export type SearchStatusApi = "running" | "completed" | "failed" | "skipped";

export interface ProviderRunOut {
  provider_id: string;
  provider_name: string;
  status: SearchStatusApi;
  results_found: number;
}

export interface SearchOut {
  id: string;
  query: string;
  location: string | null;
  status: SearchStatusApi;
  results_count: number;
  created_at: string;
  completed_at: string | null;
  provider_runs: ProviderRunOut[];
}

/** Title-case on the wire, matching the frontend's ApiProvider["category"] exactly. */
export type ProviderCategoryApi = "Search" | "Maps" | "Business" | "CRM" | "AI";
export type ProviderStatusApi = "healthy" | "degraded" | "down";

export interface ApiProviderOut {
  id: string;
  name: string;
  category: ProviderCategoryApi;
  status: ProviderStatusApi;
  logo: string | null;
  description: string | null;
  usage_count: number;
  usage_limit: number;
  latency_ms: number;
  connected: boolean;
}

/**
 * Result of a real authentication test against a provider.
 *
 * Arrives with HTTP 200 even when `success` is false — the request worked, the
 * *provider* rejected us. Callers must branch on `success`, not on the status
 * code. `details` is provider-specific diagnostics (status code, error body,
 * exception) and is safe to render verbatim.
 */
export interface ProviderTestResult {
  provider: string;
  success: boolean;
  authenticated: boolean;
  message: string;
  latency_ms: number;
  details: Record<string, unknown>;
}

/** One credential input. `is_set` says whether a value is stored — never the value. */
export interface ProviderCredentialFieldOut {
  label: string;
  env_var: string;
  is_set: boolean;
}

/**
 * Whether a provider has credentials, and which value the search pipeline uses.
 * Credential values are write-only server-side and are never returned.
 */
export interface ProviderCredentialStatusOut {
  provider_id: string;
  name: string;
  source: "workspace" | "environment" | "unset" | "none_required";
  key: ProviderCredentialFieldOut | null;
  secret: ProviderCredentialFieldOut | null;
  help_url: string | null;
}

export interface ProviderCredentialUpdateBody {
  api_key?: string;
  api_secret?: string;
}

export interface SocialLinkResult {
  platform: string;
  found: boolean;
  handle: string | null;
}

export interface WebsiteScanOut {
  id: string;
  url: string;
  domain: string;
  company_name: string | null;
  contact_person: string | null;
  confidence_score: number;
  emails: string[] | null;
  phones: string[] | null;
  gst_number: string | null;
  gst_verified: boolean;
  social_links: SocialLinkResult[] | null;
  ssl_valid: boolean;
  mobile_friendly: boolean;
  load_time_ms: number | null;
  seo_score: number | null;
  scan_duration_ms: number;
  created_at: string;
}

// --- Dashboard / analytics ----------------------------------------------

export interface DashboardStatsOut {
  total_leads: number;
  today_leads: number;
  conversion_rate: number;
  avg_lead_score: number;
  search_count: number;
  credits_remaining: number;
  credits_total: number;
}

/** The shapes below already match what the chart components render — no mapping needed. */
export interface MonthlyTrendPoint {
  month: string;
  leads: number;
  converted: number;
}
export interface NamedValuePoint {
  name: string;
  value: number;
}
export interface CountryPoint {
  country: string;
  leads: number;
}
export interface DayPoint {
  day: string;
  searches: number;
}
export interface ProviderUsagePoint {
  name: string;
  usage: number;
  limit: number;
}
export interface ExportTrendPoint {
  month: string;
  csv: number;
  excel: number;
  pdf: number;
}
export interface CityPoint {
  city: string;
  country: string | null;
  leads: number;
}
export interface LeadQualityBand {
  id: string;
  label: string;
  min_score: number;
  max_score: number;
  count: number;
  percentage: number;
}
export interface ProviderPerformancePoint {
  provider_id: string;
  name: string;
  category: string;
  status: string;
  usage: number;
  usage_limit: number;
  leads_contributed: number;
}
export interface BusinessSummaryOut {
  top_company_type: string | null;
  top_company_type_count: number;
  top_provider_name: string | null;
  top_provider_lead_count: number;
  total_companies: number;
}

// --- Notifications ------------------------------------------------------

export type NotificationTypeApi = "search" | "export" | "api" | "recommendation" | "system";

/** Note `read`, not `is_read` — already matches the frontend's NotificationItem. */
export interface NotificationOut {
  id: string;
  type: NotificationTypeApi;
  title: string;
  description: string | null;
  created_at: string;
  read: boolean;
}

export interface NotificationPreferenceOut {
  category: string;
  email_enabled: boolean;
  push_enabled: boolean;
  in_app_enabled: boolean;
}

// --- Billing ------------------------------------------------------------

export interface PlanOut {
  id: string;
  name: string;
  price_cents: number;
  currency: string;
  billing_interval: "month" | "year";
  credits_included: number;
  seats_included: number;
  features: string[];
  is_active: boolean;
}

/** One purchasable credit bundle, priced by the backend. */
export interface CreditPackOut {
  id: string;
  credits: number;
  amount_cents: number;
  currency: string;
}

export interface SubscriptionOut {
  id: string | null;
  plan: PlanOut | null;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

/**
 * Reports credits **used** against a limit — not remaining. The dashboard's
 * `credits_remaining` is a different figure from a different endpoint; mixing
 * them up silently inverts every usage bar.
 */
export interface UsageOut {
  credits_used: number;
  credits_limit: number;
  seats_used: number;
  seats_limit: number;
  searches_this_month: number;
  exports_this_month: number;
}

export interface PaymentOut {
  id: string;
  amount_cents: number;
  currency: string;
  status: "pending" | "succeeded" | "failed" | "refunded";
  payment_method_type: string | null;
  failure_reason: string | null;
  created_at: string;
}

export interface InvoiceOut {
  id: string;
  invoice_number: string;
  amount_cents: number;
  currency: string;
  status: "paid" | "pending" | "failed";
  invoice_pdf_url: string | null;
  period_start: string | null;
  period_end: string | null;
  created_at: string;
}

export interface TransactionOut {
  id: string;
  type: "subscription_charge" | "credit_topup" | "credit_usage" | "refund";
  amount_cents: number;
  /** Signed: negative for usage, positive for top-ups. */
  credits_delta: number;
  balance_after: number;
  description: string | null;
  created_at: string;
}

export interface CheckoutSessionOut {
  checkout_url: string;
}

// --- Exports ------------------------------------------------------------

export type ExportFormatApi = "csv" | "excel" | "pdf" | "json";
export type ExportStatusApi = "processing" | "ready" | "expired" | "failed";
export type ExportResourceApi =
  | "leads"
  | "search_results"
  | "dashboard_report"
  | "analytics_report";
export type ExportScopeApi = "all" | "filtered" | "selected";

export interface ExportFiltersBody {
  search?: string | null;
  industry?: string | null;
  status?: string | null;
  country?: string | null;
  min_score?: number | null;
  max_score?: number | null;
  sort_by?: "created_at" | "lead_score" | "company";
  sort_order?: "asc" | "desc";
}

export interface ExportCreateBody {
  resource?: ExportResourceApi;
  format?: ExportFormatApi;
  scope?: ExportScopeApi;
  lead_ids?: string[];
  filters?: ExportFiltersBody | null;
  search_id?: string | null;
  columns?: string[];
  file_name?: string | null;
}

export interface ExportOut {
  id: string;
  file_name: string;
  format: ExportFormatApi;
  resource: ExportResourceApi;
  row_count: number;
  size_bytes: number;
  size_label: string;
  status: ExportStatusApi;
  download_count: number;
  created_at: string;
  expires_at: string | null;
  error_message: string | null;
  /** Root-relative (/api/v1/...). Join against the API ORIGIN, not the versioned base. */
  download_url: string | null;
  ignored_columns: string[];
}

export interface DownloadTokenOut {
  token: string;
  expires_in: number;
  /** Root-relative, token already attached. */
  download_url: string;
}

export interface ExportOptionsOut {
  formats: { value: ExportFormatApi; extension: string; media_type: string }[];
  resources: ExportResourceApi[];
  scopes: ExportScopeApi[];
  lead_columns: { key: string; label: string }[];
  default_lead_columns: string[];
  limits: {
    max_rows: number;
    max_file_size_mb: number;
    async_row_threshold: number;
    retention_hours: number;
    rate_limit_per_hour: number;
  };
}

// --- Settings -----------------------------------------------------------

/** The settings-scoped profile (richer than the one nested on UserOut). */
export interface ProfileOut {
  id: string;
  email: string;
  phone: string | null;
  full_name: string | null;
  avatar_url: string | null;
  job_title: string | null;
  timezone: string;
  locale: string;
}

export interface ProfileUpdateBody {
  full_name?: string | null;
  job_title?: string | null;
  phone?: string | null;
  timezone?: string | null;
  locale?: string | null;
}

export interface OrganizationOut {
  id: string;
  name: string;
  industry: string | null;
  company_size: string | null;
  website: string | null;
  logo_url: string | null;
  timezone: string;
  locale: string;
  created_at: string;
}

export interface OrganizationUpdateBody {
  name?: string | null;
  industry?: string | null;
  company_size?: string | null;
  website?: string | null;
  timezone?: string | null;
  locale?: string | null;
}

export interface ApiKeyOut {
  id: string;
  name: string;
  key_prefix: string;
  /** Display form, e.g. "lm_live_abc…xyz". */
  masked: string;
  last_used_at: string | null;
  created_at: string;
}

/** Creation is the only time the full key is returned. */
export interface ApiKeyCreateResponse extends ApiKeyOut {
  key: string;
}

export interface BackupSnapshotOut {
  id: string;
  label: string;
  size_bytes: number;
  status: string;
  created_at: string;
}

/** Generic key/value store used by the theme and misc preferences. */
export interface SettingOut {
  scope: string;
  key: string;
  value: unknown;
}

// --- Team ---------------------------------------------------------------

export type RoleNameApi = "owner" | "admin" | "member" | "viewer" | "superadmin";

export interface MemberOut {
  /** Membership row id. Use `user_id` for member-scoped routes. */
  id: string;
  user_id: string;
  name: string | null;
  email: string;
  avatar_url: string | null;
  role: RoleNameApi;
  status: string;
  joined_at: string | null;
  last_active: string | null;
}

export interface PermissionOut {
  code: string;
  description: string | null;
}

export interface RolePermissionsOut {
  role: RoleNameApi;
  permissions: string[];
}

export interface InvitationOut {
  id: string;
  email: string;
  role: RoleNameApi;
  invited_by: string | null;
  status: string;
  created_at: string;
  expires_at: string;
}

// --- Map ----------------------------------------------------------------

export interface GeocodeResult {
  lat: number;
  lng: number;
  formatted_address: string;
}

export interface NearbyLeadOut {
  lead_id: string;
  company_name: string;
  lat: number;
  lng: number;
  distance_km: number;
  lead_score: number;
  industry: string | null;
  city: string | null;
}

// --- Files -------------------------------------------------------------

export interface DocumentOut {
  id: string;
  file_name: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
  download_url: string;
}
