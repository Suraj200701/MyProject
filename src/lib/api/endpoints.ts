/**
 * Every backend call the app makes, grouped by domain.
 *
 * Thin by design: each function is one `apiFetch` with typed input and output.
 * Response *shaping* lives in `mappers.ts` and caching lives in the query hooks,
 * so this file stays a readable index of the API surface — if an endpoint isn't
 * here, the app doesn't call it.
 */

import { apiFetch, apiFetchBlob, absoluteUrl } from "@/lib/api/client";
import type {
  ProviderCredentialUpdateBody,
  ProviderCredentialStatusOut,
  PermissionOut,
  RolePermissionsOut,
  CreditPackOut,
  ApiKeyCreateResponse,
  ApiKeyOut,
  ApiProviderOut,
  BackupSnapshotOut,
  BusinessSummaryOut,
  CheckoutSessionOut,
  CityPoint,
  CountryPoint,
  CsvImportResult,
  DashboardStatsOut,
  DataResponse,
  DayPoint,
  DocumentOut,
  DownloadTokenOut,
  ExportCreateBody,
  ExportOptionsOut,
  ExportOut,
  ExportResourceApi,
  ExportStatusApi,
  GeocodeResult,
  InvitationOut,
  InvoiceOut,
  LeadCreateBody,
  LeadDetailOut,
  LeadNoteOut,
  LeadOut,
  LeadQualityBand,
  LeadUpdateBody,
  MemberOut,
  MessageResponse,
  MonthlyTrendPoint,
  NamedValuePoint,
  NearbyLeadOut,
  NotificationOut,
  NotificationPreferenceOut,
  OrganizationOut,
  OrganizationUpdateBody,
  Page,
  PaymentOut,
  PlanOut,
  ProfileOut,
  ProfileUpdateBody,
  ProviderPerformancePoint,
  ProviderUsagePoint,
  RoleNameApi,
  SearchOut,
  SessionOut,
  SettingOut,
  SubscriptionOut,
  TokenResponse,
  TransactionOut,
  UsageOut,
  UserOut,
  WebsiteScanOut,
  ExportTrendPoint,
} from "@/lib/api/types";

// --- Auth ----------------------------------------------------------------

/** Type alias, not an interface — see QueryParams in client.ts for why. */
export type PaginationQuery = {
  page?: number;
  page_size?: number;
};

export const authApi = {
  signup: (body: { email: string; password: string; full_name: string; company_name: string }) =>
    apiFetch<TokenResponse>("/auth/signup", { method: "POST", body, anonymous: true }),

  login: (body: { email: string; password: string; remember_me?: boolean }) =>
    apiFetch<TokenResponse>("/auth/login", { method: "POST", body, anonymous: true }),

  /** Invalidates the refresh token server-side. */
  logout: (refresh_token: string) =>
    apiFetch<MessageResponse>("/auth/logout", { method: "POST", body: { refresh_token } }),

  me: () => apiFetch<UserOut>("/auth/me"),

  changePassword: (body: { current_password: string; new_password: string }) =>
    apiFetch<MessageResponse>("/auth/change-password", { method: "POST", body }),

  forgotPassword: (email: string) =>
    apiFetch<MessageResponse>("/auth/forgot-password", {
      method: "POST",
      body: { email },
      anonymous: true,
    }),

  resetPassword: (body: { token: string; new_password: string }) =>
    apiFetch<MessageResponse>("/auth/reset-password", { method: "POST", body, anonymous: true }),

  verifyEmail: (token: string) =>
    apiFetch<MessageResponse>("/auth/verify-email", {
      method: "POST",
      body: { token },
      anonymous: true,
    }),

  resendVerification: () => apiFetch<MessageResponse>("/auth/resend-verification", { method: "POST" }),

  /** Sends a one-time code. `purpose` defaults to login on the backend. */
  requestOtp: (body: { email: string; purpose?: string }) =>
    apiFetch<MessageResponse>("/auth/otp/request", { method: "POST", body, anonymous: true }),

  /** Exchanges a valid code for a token pair. */
  verifyOtp: (body: { email: string; code: string; purpose?: string }) =>
    apiFetch<TokenResponse>("/auth/otp/verify", { method: "POST", body, anonymous: true }),

  sessions: () => apiFetch<SessionOut[]>("/auth/sessions"),

  revokeSession: (sessionId: string) =>
    apiFetch<MessageResponse>(`/auth/sessions/${sessionId}`, { method: "DELETE" }),

  /** Full-page redirect target for the Google OAuth flow. */
  googleLoginUrl: () => absoluteUrl("/api/v1/auth/google/login"),

  /**
   * Whether Google sign-in is usable on this deployment.
   *
   * The login endpoint 400s with an explanatory message when `GOOGLE_CLIENT_ID`
   * is unset. Because starting OAuth is a **full-page navigation**, there is no
   * way to catch that 400 after the fact — the user would simply land on a JSON
   * error page. So the button probes first and only navigates if the server can
   * actually start the flow.
   *
   * `redirect: "manual"` keeps the browser from following the 307 to Google when
   * it *is* configured; an opaque redirect response is the success signal.
   */
  isGoogleOAuthAvailable: async (): Promise<{ available: boolean; reason?: string }> => {
    try {
      const response = await fetch(absoluteUrl("/api/v1/auth/google/login"), {
        method: "GET",
        redirect: "manual",
      });
      // An opaque redirect (type "opaqueredirect", status 0) means the backend
      // issued a redirect to Google — configured and working.
      if (response.type === "opaqueredirect" || response.status === 0 || response.ok) {
        return { available: true };
      }
      const body = (await response.json().catch(() => null)) as { message?: string } | null;
      return { available: false, reason: body?.message };
    } catch {
      return { available: false, reason: "Could not reach the server." };
    }
  },
};

// --- Leads ---------------------------------------------------------------

export type LeadsQuery = PaginationQuery & {
  search?: string;
  industry?: string;
  status?: string;
  country?: string;
  min_score?: number;
  max_score?: number;
  sort_by?: "created_at" | "lead_score" | "company";
  sort_order?: "asc" | "desc";
};

export const leadsApi = {
  list: (query: LeadsQuery = {}) => apiFetch<Page<LeadOut>>("/leads", { query }),

  get: (leadId: string) => apiFetch<LeadDetailOut>(`/leads/${leadId}`),

  create: (body: LeadCreateBody) => apiFetch<LeadOut>("/leads", { method: "POST", body }),

  update: (leadId: string, body: LeadUpdateBody) =>
    apiFetch<LeadOut>(`/leads/${leadId}`, { method: "PATCH", body }),

  remove: (leadId: string) => apiFetch<MessageResponse>(`/leads/${leadId}`, { method: "DELETE" }),

  bulkRemove: (ids: string[]) =>
    apiFetch<MessageResponse>("/leads/bulk-delete", { method: "POST", body: { ids } }),

  notes: (leadId: string) => apiFetch<LeadNoteOut[]>(`/leads/${leadId}/notes`),

  addNote: (leadId: string, text: string) =>
    apiFetch<LeadNoteOut>(`/leads/${leadId}/notes`, { method: "POST", body: { text } }),

  /** Multipart upload; the browser sets the boundary, so no Content-Type here. */
  importCsv: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetch<CsvImportResult>("/leads/import", { method: "POST", formData });
  },
};

// --- Search / providers / scanner ---------------------------------------

export const searchApi = {
  run: (body: { query: string; location?: string; industry?: string; country?: string }) =>
    apiFetch<SearchOut>("/search", { method: "POST", body }),

  history: (query: PaginationQuery = {}) => apiFetch<Page<SearchOut>>("/search/history", { query }),

  providers: () => apiFetch<ApiProviderOut[]>("/providers"),
  providerCredentials: () =>
    apiFetch<ProviderCredentialStatusOut[]>("/providers/credentials"),
  setProviderCredentials: (providerId: string, body: ProviderCredentialUpdateBody) =>
    apiFetch<ProviderCredentialStatusOut>(`/providers/${providerId}/credentials`, {
      method: "PUT",
      body,
    }),
  clearProviderCredentials: (providerId: string) =>
    apiFetch<ProviderCredentialStatusOut>(`/providers/${providerId}/credentials`, {
      method: "DELETE",
    }),

  scanWebsite: (url: string) =>
    apiFetch<WebsiteScanOut>("/scan-website", { method: "POST", body: { url } }),

  scans: (query: PaginationQuery = {}) => apiFetch<Page<WebsiteScanOut>>("/scans", { query }),
};

// --- Dashboard ----------------------------------------------------------

export const dashboardApi = {
  stats: () => apiFetch<DashboardStatsOut>("/dashboard/stats"),
  leadGrowth: () => apiFetch<MonthlyTrendPoint[]>("/dashboard/lead-growth"),
  industryDistribution: () => apiFetch<NamedValuePoint[]>("/dashboard/industry-distribution"),
  countryAnalytics: () => apiFetch<CountryPoint[]>("/dashboard/country-analytics"),
  searchAnalytics: () => apiFetch<DayPoint[]>("/dashboard/search-analytics"),
  apiUsage: () => apiFetch<ProviderUsagePoint[]>("/dashboard/api-usage"),
  exportAnalytics: () => apiFetch<ExportTrendPoint[]>("/dashboard/export-analytics"),
};

// --- Analytics ----------------------------------------------------------

export const analyticsApi = {
  topIndustries: () => apiFetch<NamedValuePoint[]>("/analytics/top-industries"),
  topCities: () => apiFetch<CityPoint[]>("/analytics/top-cities"),
  leadQuality: () => apiFetch<LeadQualityBand[]>("/analytics/lead-quality"),
  providerPerformance: () => apiFetch<ProviderPerformancePoint[]>("/analytics/provider-performance"),
  businessSummary: () => apiFetch<BusinessSummaryOut>("/analytics/business-summary"),
};

// --- Notifications ------------------------------------------------------

export const notificationsApi = {
  list: (query: PaginationQuery & { unread_only?: boolean } = {}) =>
    apiFetch<Page<NotificationOut>>("/notifications", { query }),

  unreadCount: () => apiFetch<DataResponse<number>>("/notifications/unread-count"),

  markRead: (notificationId: string) =>
    apiFetch<MessageResponse>(`/notifications/${notificationId}/read`, { method: "POST" }),

  markAllRead: () => apiFetch<MessageResponse>("/notifications/read-all", { method: "POST" }),

  preferences: () => apiFetch<NotificationPreferenceOut[]>("/notifications/preferences"),

  updatePreference: (
    category: string,
    body: { email_enabled?: boolean; push_enabled?: boolean; in_app_enabled?: boolean },
  ) =>
    apiFetch<NotificationPreferenceOut>(`/notifications/preferences/${category}`, {
      method: "PATCH",
      body,
    }),
};

// --- Billing ------------------------------------------------------------

export const billingApi = {
  plans: () => apiFetch<PlanOut[]>("/billing/plans"),
  creditPacks: () => apiFetch<CreditPackOut[]>("/billing/credit-packs"),
  subscription: () => apiFetch<SubscriptionOut>("/billing/subscription"),
  usage: () => apiFetch<UsageOut>("/billing/usage"),
  payments: (query: PaginationQuery = {}) => apiFetch<Page<PaymentOut>>("/billing/payments", { query }),
  invoices: (query: PaginationQuery = {}) => apiFetch<Page<InvoiceOut>>("/billing/invoices", { query }),
  transactions: (query: PaginationQuery = {}) =>
    apiFetch<Page<TransactionOut>>("/billing/transactions", { query }),

  /** Returns a Stripe Checkout URL to redirect to. 400s when Stripe isn't configured. */
  checkout: (plan_id: string) =>
    apiFetch<CheckoutSessionOut>("/billing/checkout", { method: "POST", body: { plan_id } }),

  topUpCredits: (body: { amount_cents?: number; pack_id?: string }) =>
    apiFetch<CheckoutSessionOut>("/billing/credits/checkout", { method: "POST", body }),
};

// --- Exports ------------------------------------------------------------

export const exportsApi = {
  create: (body: ExportCreateBody) => apiFetch<ExportOut>("/exports", { method: "POST", body }),

  list: (query: PaginationQuery & { resource?: ExportResourceApi; status?: ExportStatusApi } = {}) =>
    apiFetch<Page<ExportOut>>("/exports", { query }),

  get: (exportId: string) => apiFetch<ExportOut>(`/exports/${exportId}`),

  options: () => apiFetch<ExportOptionsOut>("/exports/formats"),

  remove: (exportId: string) =>
    apiFetch<MessageResponse>(`/exports/${exportId}`, { method: "DELETE" }),

  /**
   * Mints a signed token, then hands back an absolute URL usable without an
   * Authorization header — which is what a browser download needs.
   */
  downloadUrl: async (exportId: string): Promise<string> => {
    const token = await apiFetch<DownloadTokenOut>(`/exports/${exportId}/download-token`, {
      method: "POST",
    });
    return absoluteUrl(token.download_url);
  },

  /** Fetches the bytes with bearer auth instead, for a save-as flow. */
  downloadBlob: (exportId: string) => apiFetchBlob(`/exports/${exportId}/download`),
};

// --- Settings -----------------------------------------------------------

export const settingsApi = {
  profile: () => apiFetch<ProfileOut>("/settings/profile"),
  updateProfile: (body: ProfileUpdateBody) =>
    apiFetch<ProfileOut>("/settings/profile", { method: "PATCH", body }),

  organization: () => apiFetch<OrganizationOut>("/settings/organization"),
  updateOrganization: (body: OrganizationUpdateBody) =>
    apiFetch<OrganizationOut>("/settings/organization", { method: "PATCH", body }),

  apiKeys: () => apiFetch<ApiKeyOut[]>("/settings/api-keys"),
  createApiKey: (name: string) =>
    apiFetch<ApiKeyCreateResponse>("/settings/api-keys", { method: "POST", body: { name } }),
  revokeApiKey: (keyId: string) =>
    apiFetch<MessageResponse>(`/settings/api-keys/${keyId}`, { method: "DELETE" }),

  backups: () => apiFetch<BackupSnapshotOut[]>("/settings/backups"),
  createBackup: (label?: string) =>
    apiFetch<BackupSnapshotOut>("/settings/backups", { method: "POST", body: { label } }),

  /** Generic key/value store, used for the theme preference. */
  getSetting: (scope: string, key: string) => apiFetch<SettingOut>(`/settings/${scope}/${key}`),
  putSetting: (scope: string, key: string, value: unknown) =>
    apiFetch<SettingOut>(`/settings/${scope}/${key}`, { method: "PUT", body: { key, value } }),
};

// --- Team ---------------------------------------------------------------

export const teamApi = {
  members: () => apiFetch<MemberOut[]>("/team/members"),
  invitations: () => apiFetch<InvitationOut[]>("/team/invitations"),
  /** Role -> permission-code matrix, as enforced by the API. */
  roles: () => apiFetch<RolePermissionsOut[]>("/team/roles"),
  permissions: () => apiFetch<PermissionOut[]>("/team/permissions"),

  invite: (body: { email: string; role?: RoleNameApi }) =>
    apiFetch<InvitationOut>("/team/invite", { method: "POST", body }),

  resendInvitation: (invitationId: string) =>
    apiFetch<MessageResponse>(`/team/invitations/${invitationId}/resend`, { method: "POST" }),

  revokeInvitation: (invitationId: string) =>
    apiFetch<MessageResponse>(`/team/invitations/${invitationId}`, { method: "DELETE" }),

  acceptInvitation: (token: string) =>
    apiFetch<MessageResponse>("/team/invitations/accept", { method: "POST", body: { token } }),

  /** Member-scoped routes key on `user_id`, not the membership row id. */
  updateMemberRole: (memberUserId: string, role: RoleNameApi) =>
    apiFetch<MemberOut>(`/team/members/${memberUserId}/role`, { method: "PATCH", body: { role } }),

  removeMember: (memberUserId: string) =>
    apiFetch<MessageResponse>(`/team/members/${memberUserId}`, { method: "DELETE" }),
};

// --- Map ----------------------------------------------------------------

export const mapApi = {
  geocode: (address: string) =>
    apiFetch<GeocodeResult>("/map/geocode", { method: "POST", body: { address } }),

  /** Pure database + haversine; needs no API key. */
  nearbyLeads: (body: { lat: number; lng: number; radius_km?: number; industry?: string }) =>
    apiFetch<NearbyLeadOut[]>("/map/nearby-leads", { method: "POST", body }),

  reverseGeocode: (lat: number, lng: number) =>
    apiFetch<GeocodeResult>("/map/reverse-geocode", { query: { lat, lng } }),
};

// --- Files -------------------------------------------------------------

export const filesApi = {
  list: (query: PaginationQuery & { entity_type?: string } = {}) =>
    apiFetch<Page<DocumentOut>>("/files", { query }),

  upload: (file: File, options: { kind?: "image" | "document"; entity_type?: string } = {}) => {
    const formData = new FormData();
    formData.append("file", file);
    if (options.kind) formData.append("kind", options.kind);
    if (options.entity_type) formData.append("entity_type", options.entity_type);
    return apiFetch<{ success: boolean; document: DocumentOut }>("/files/upload", {
      method: "POST",
      formData,
    });
  },

  remove: (documentId: string) =>
    apiFetch<MessageResponse>(`/files/${documentId}`, { method: "DELETE" }),
};
