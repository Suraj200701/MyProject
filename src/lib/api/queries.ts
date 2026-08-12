"use client";

/**
 * TanStack Query hooks — the layer components actually call.
 *
 * Conventions:
 *   * Query keys are arrays namespaced by domain (`["leads", "list", params]`),
 *     so a mutation can invalidate a whole domain with one prefix.
 *   * List hooks return already-mapped view models, so components receive the
 *     exact shapes they were written against.
 *   * Mutations invalidate rather than hand-patch the cache: the backend derives
 *     values the client can't (lead scores, credit balances, dedup outcomes), so
 *     refetching is the only way to stay truthful.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";

import {
  analyticsApi,
  authApi,
  enrichmentApi,
  billingApi,
  dashboardApi,
  exportsApi,
  leadsApi,
  mapApi,
  notificationsApi,
  importsApi,
  searchApi,
  settingsApi,
  teamApi,
  type LeadsQuery,
  type PaginationQuery,
} from "@/lib/api/endpoints";
import {
  toApiProviders,
  toDashboardStats,
  toLead,
  toLeads,
  toNearbyLead,
  toNotifications,
  toSearchHistory,
} from "@/lib/api/mappers";
import type {
  ExportCreateBody,
  ExportResourceApi,
  ExportStatusApi,
  ImportSource,
  LeadCreateBody,
  LeadUpdateBody,
  MapResult,
  MapSource,
  MapViewport,
  ProviderCredentialUpdateBody,
  RoleNameApi,
  SearchMode,
} from "@/lib/api/types";

/** Central key registry, so invalidations can't drift from the queries. */
export const queryKeys = {
  dashboard: ["dashboard"] as const,
  analytics: ["analytics"] as const,
  leads: ["leads"] as const,
  lead: (id: string) => ["leads", "detail", id] as const,
  searches: ["searches"] as const,
  providers: ["providers"] as const,
  scans: ["scans"] as const,
  notifications: ["notifications"] as const,
  exports: ["exports"] as const,
  billing: ["billing"] as const,
  settings: ["settings"] as const,
  team: ["team"] as const,
  map: ["map"] as const,
  imports: ["imports"] as const,
};

/**
 * Reference data that rarely changes within a session.
 * Longer than the 60s app default to avoid refetching plan lists on every mount.
 */
const STATIC_DATA = { staleTime: 5 * 60_000 } satisfies Partial<UseQueryOptions>;

// --- Dashboard ----------------------------------------------------------

export function useDashboardStats() {
  return useQuery({
    queryKey: [...queryKeys.dashboard, "stats"],
    queryFn: async () => toDashboardStats(await dashboardApi.stats()),
  });
}

export function useLeadGrowth() {
  return useQuery({
    queryKey: [...queryKeys.dashboard, "lead-growth"],
    queryFn: dashboardApi.leadGrowth,
  });
}

export function useIndustryDistribution() {
  return useQuery({
    queryKey: [...queryKeys.dashboard, "industry-distribution"],
    queryFn: dashboardApi.industryDistribution,
  });
}

export function useCountryAnalytics() {
  return useQuery({
    queryKey: [...queryKeys.dashboard, "country-analytics"],
    queryFn: dashboardApi.countryAnalytics,
  });
}

export function useSearchAnalytics() {
  return useQuery({
    queryKey: [...queryKeys.dashboard, "search-analytics"],
    queryFn: dashboardApi.searchAnalytics,
  });
}

export function useApiUsage() {
  return useQuery({
    queryKey: [...queryKeys.dashboard, "api-usage"],
    queryFn: dashboardApi.apiUsage,
  });
}

export function useExportAnalytics() {
  return useQuery({
    queryKey: [...queryKeys.dashboard, "export-analytics"],
    queryFn: dashboardApi.exportAnalytics,
  });
}

// --- Analytics ----------------------------------------------------------

export function useTopIndustries() {
  return useQuery({
    queryKey: [...queryKeys.analytics, "top-industries"],
    queryFn: analyticsApi.topIndustries,
  });
}

export function useTopCities() {
  return useQuery({
    queryKey: [...queryKeys.analytics, "top-cities"],
    queryFn: analyticsApi.topCities,
  });
}

export function useLeadQuality() {
  return useQuery({
    queryKey: [...queryKeys.analytics, "lead-quality"],
    queryFn: analyticsApi.leadQuality,
  });
}

export function useProviderPerformance() {
  return useQuery({
    queryKey: [...queryKeys.analytics, "provider-performance"],
    queryFn: analyticsApi.providerPerformance,
  });
}

export function useBusinessSummary() {
  return useQuery({
    queryKey: [...queryKeys.analytics, "business-summary"],
    queryFn: analyticsApi.businessSummary,
  });
}

// --- Leads --------------------------------------------------------------

export function useLeads(query: LeadsQuery = {}) {
  return useQuery({
    queryKey: [...queryKeys.leads, "list", query],
    queryFn: async () => {
      const page = await leadsApi.list(query);
      return { items: toLeads(page.items), meta: page.meta };
    },
    // Keeps the previous page rendered while the next one loads, so the table
    // doesn't collapse to a skeleton on every pagination click.
    placeholderData: (previous) => previous,
  });
}

export function useLead(leadId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.lead(leadId ?? ""),
    enabled: !!leadId,
    queryFn: async () => {
      const detail = await leadsApi.get(leadId!);
      return {
        lead: toLead(detail),
        notes: detail.notes ?? [],
        activities: detail.activities ?? [],
      };
    },
  });
}

export function useCreateLead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: LeadCreateBody) => leadsApi.create(body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.leads });
      // A new lead moves the dashboard's totals and distributions.
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

export function useUpdateLead(leadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: LeadUpdateBody) => leadsApi.update(leadId, body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.lead(leadId) });
      client.invalidateQueries({ queryKey: queryKeys.leads });
      // A status change alters the conversion rate.
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

export function useDeleteLeads() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) =>
      ids.length === 1 ? leadsApi.remove(ids[0]) : leadsApi.bulkRemove(ids),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.leads });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

export function useAddLeadNote(leadId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => leadsApi.addNote(leadId, text),
    // The backend also writes a timeline activity, so refetch the whole detail.
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.lead(leadId) }),
  });
}

export function useImportLeadsCsv() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => leadsApi.importCsv(file),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.leads });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

// --- Search / providers / scanner ---------------------------------------

export function useSearchHistory(query: PaginationQuery = {}) {
  return useQuery({
    queryKey: [...queryKeys.searches, "history", query],
    queryFn: async () => {
      const page = await searchApi.history(query);
      return { items: toSearchHistory(page.items), meta: page.meta, raw: page.items };
    },
  });
}

export function useRunSearch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      query: string;
      location?: string;
      industry?: string;
      country?: string;
      /** Omit to query every configured provider (pre-Lead-Source behaviour). */
      mode?: SearchMode;
    }) => searchApi.run(body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.searches });
      client.invalidateQueries({ queryKey: queryKeys.leads });
      // A search spends credits and adds leads.
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.analytics });
      client.invalidateQueries({ queryKey: queryKeys.providers });
    },
  });
}

export function useProviders() {
  return useQuery({
    queryKey: queryKeys.providers,
    queryFn: async () => toApiProviders(await searchApi.providers()),
    ...STATIC_DATA,
  });
}

/**
 * Credential *status* for every provider — never the credential values, which
 * the backend refuses to return. Gated on `api_keys.manage`, so this 403s for
 * roles that cannot manage providers; callers should treat that as "hide the
 * form" rather than as an error.
 */
export function useProviderCredentials(enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.providers, "credentials"],
    queryFn: searchApi.providerCredentials,
    enabled,
    retry: false,
  });
}

export function useSetProviderCredentials() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ providerId, ...body }: { providerId: string } & ProviderCredentialUpdateBody) =>
      searchApi.setProviderCredentials(providerId, body),
    // `connected` on the provider row changes too, so refresh the whole domain.
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.providers }),
  });
}

export function useClearProviderCredentials() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (providerId: string) => searchApi.clearProviderCredentials(providerId),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.providers }),
  });
}

/**
 * Runs a real authentication test against one provider.
 *
 * A failed *test* is a fulfilled mutation carrying `success: false` — only a
 * transport or permission error rejects. So `onSuccess` fires either way, which
 * is what we want: the server records the measured latency and may downgrade the
 * provider's status on failure, and both belong in the refreshed provider list.
 */
export function useTestProvider() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (providerId: string) => searchApi.testProvider(providerId),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.providers }),
  });
}

/** Real checks against SMTP, Stripe, Redis and Postgres. */
export function useSystemChecks() {
  return useMutation({ mutationFn: searchApi.systemChecks });
}

/** Import history, newest first. Optionally filtered to one source. */
/**
 * Saves a website scan as a lead.
 *
 * Invalidates leads, scans and the dashboard: the scan row gains a `lead_id`, a
 * lead appears, and every count on screen shifts. Leaving them stale reads as the
 * save having done nothing — which is exactly the bug this replaced.
 */
export function useSaveScanAsLead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (scanId: string) => searchApi.saveScanAsLead(scanId),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.leads });
      client.invalidateQueries({ queryKey: queryKeys.scans });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

export function useImportHistory(query: PaginationQuery & { source?: ImportSource } = {}) {
  return useQuery({
    queryKey: [...queryKeys.imports, query],
    queryFn: () => importsApi.history(query),
  });
}

/**
 * Uploads a Google Maps extractor CSV and runs the import pipeline.
 *
 * Invalidates leads and the dashboard as well as history: an import that adds
 * hundreds of leads makes every count on screen stale, and leaving them showing
 * pre-import numbers reads as the import having done nothing.
 */
export function useImportGoogleMapsCsv() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: importsApi.importGoogleMaps,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.imports });
      client.invalidateQueries({ queryKey: queryKeys.leads });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

/** Asks the backend for the Google Maps URL to open. Never fetches Maps itself. */
export function useMapsSearchUrl() {
  return useMutation({
    mutationFn: ({ keyword, location }: { keyword: string; location?: string }) =>
      importsApi.mapsSearchUrl(keyword, location),
  });
}

export function useScans(query: PaginationQuery = {}) {
  return useQuery({
    queryKey: [...queryKeys.scans, query],
    queryFn: async () => {
      const page = await searchApi.scans(query);
      return { items: page.items, meta: page.meta };
    },
  });
}

export function useScanWebsite() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => searchApi.scanWebsite(url),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.scans });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

// --- Notifications ------------------------------------------------------

export function useNotifications(query: PaginationQuery & { unread_only?: boolean } = {}) {
  return useQuery({
    queryKey: [...queryKeys.notifications, "list", query],
    queryFn: async () => {
      const page = await notificationsApi.list(query);
      return { items: toNotifications(page.items), meta: page.meta };
    },
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: [...queryKeys.notifications, "unread-count"],
    queryFn: async () => (await notificationsApi.unreadCount()).data,
    // The bell badge should track reality without a page refresh.
    refetchInterval: 60_000,
  });
}

export function useMarkNotificationRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.notifications }),
  });
}

export function useMarkAllNotificationsRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.notifications }),
  });
}

export function useNotificationPreferences() {
  return useQuery({
    queryKey: [...queryKeys.notifications, "preferences"],
    queryFn: notificationsApi.preferences,
  });
}

export function useUpdateNotificationPreference() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      category,
      ...body
    }: {
      category: string;
      email_enabled?: boolean;
      push_enabled?: boolean;
      in_app_enabled?: boolean;
    }) => notificationsApi.updatePreference(category, body),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: [...queryKeys.notifications, "preferences"] }),
  });
}

// --- Billing ------------------------------------------------------------

export function usePlans() {
  return useQuery({
    queryKey: [...queryKeys.billing, "plans"],
    queryFn: billingApi.plans,
    ...STATIC_DATA,
  });
}

/** Credit top-up catalogue. Priced server-side; changes only on deploy. */
export function useCreditPacks() {
  return useQuery({
    queryKey: [...queryKeys.billing, "credit-packs"],
    queryFn: billingApi.creditPacks,
    staleTime: Infinity,
  });
}

export function useSubscription() {
  return useQuery({
    queryKey: [...queryKeys.billing, "subscription"],
    queryFn: billingApi.subscription,
  });
}

export function useUsage() {
  return useQuery({ queryKey: [...queryKeys.billing, "usage"], queryFn: billingApi.usage });
}

export function useInvoices(query: PaginationQuery = {}) {
  return useQuery({
    queryKey: [...queryKeys.billing, "invoices", query],
    queryFn: () => billingApi.invoices(query),
  });
}

export function useTransactions(query: PaginationQuery = {}) {
  return useQuery({
    queryKey: [...queryKeys.billing, "transactions", query],
    queryFn: () => billingApi.transactions(query),
  });
}

export function useCheckout() {
  return useMutation({ mutationFn: (planId: string) => billingApi.checkout(planId) });
}

export function useCreditTopUp() {
  return useMutation({
    mutationFn: (body: { amount_cents?: number; pack_id?: string }) =>
      billingApi.topUpCredits(body),
  });
}

// --- Exports ------------------------------------------------------------

export function useExports(
  query: PaginationQuery & { resource?: ExportResourceApi; status?: ExportStatusApi } = {},
) {
  return useQuery({
    queryKey: [...queryKeys.exports, "list", query],
    queryFn: () => exportsApi.list(query),
  });
}

export function useExportOptions() {
  return useQuery({
    queryKey: [...queryKeys.exports, "options"],
    queryFn: exportsApi.options,
    ...STATIC_DATA,
  });
}

/**
 * Polls a single export until it leaves `processing`.
 *
 * Only enabled for background exports; an inline export is already `ready` when
 * the create call returns, so this never fires for the common case.
 */
export function useExportStatus(exportId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: [...queryKeys.exports, "status", exportId],
    enabled: !!exportId && enabled,
    queryFn: () => exportsApi.get(exportId!),
    refetchInterval: (query) => (query.state.data?.status === "processing" ? 2_000 : false),
  });
}

export function useCreateExport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ExportCreateBody) => exportsApi.create(body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.exports });
      client.invalidateQueries({ queryKey: [...queryKeys.dashboard, "export-analytics"] });
    },
  });
}

export function useDeleteExport() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (exportId: string) => exportsApi.remove(exportId),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.exports }),
  });
}

// --- Settings -----------------------------------------------------------

export function useProfile() {
  return useQuery({ queryKey: [...queryKeys.settings, "profile"], queryFn: settingsApi.profile });
}

export function useUpdateProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.updateProfile,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: [...queryKeys.settings, "profile"] });
      // The topbar avatar/name come from the auth user.
      client.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useOrganization() {
  return useQuery({
    queryKey: [...queryKeys.settings, "organization"],
    queryFn: settingsApi.organization,
  });
}

export function useUpdateOrganization() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.updateOrganization,
    onSuccess: () => client.invalidateQueries({ queryKey: [...queryKeys.settings, "organization"] }),
  });
}

export function useApiKeys() {
  return useQuery({ queryKey: [...queryKeys.settings, "api-keys"], queryFn: settingsApi.apiKeys });
}

export function useCreateApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => settingsApi.createApiKey(name),
    onSuccess: () => client.invalidateQueries({ queryKey: [...queryKeys.settings, "api-keys"] }),
  });
}

export function useRevokeApiKey() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => settingsApi.revokeApiKey(keyId),
    onSuccess: () => client.invalidateQueries({ queryKey: [...queryKeys.settings, "api-keys"] }),
  });
}

export function useBackups() {
  return useQuery({ queryKey: [...queryKeys.settings, "backups"], queryFn: settingsApi.backups });
}

export function useCreateBackup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (label?: string) => settingsApi.createBackup(label),
    onSuccess: () => client.invalidateQueries({ queryKey: [...queryKeys.settings, "backups"] }),
  });
}

export function useSessions() {
  return useQuery({ queryKey: ["auth", "sessions"], queryFn: authApi.sessions });
}

export function useRevokeSession() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => authApi.revokeSession(sessionId),
    onSuccess: () => client.invalidateQueries({ queryKey: ["auth", "sessions"] }),
  });
}

export function useChangePassword() {
  return useMutation({ mutationFn: authApi.changePassword });
}

// --- Team ---------------------------------------------------------------

export function useTeamMembers() {
  return useQuery({ queryKey: [...queryKeys.team, "members"], queryFn: teamApi.members });
}

export function useTeamInvitations() {
  return useQuery({ queryKey: [...queryKeys.team, "invitations"], queryFn: teamApi.invitations });
}

/**
 * Role -> permission matrix and the permission catalogue.
 *
 * Both are seeded reference data that only changes on deploy, so they are
 * cached for the session rather than refetched with the rest of the team data.
 */
export function useRolePermissions() {
  return useQuery({
    queryKey: [...queryKeys.team, "roles"],
    queryFn: teamApi.roles,
    staleTime: Infinity,
  });
}

export function usePermissionCatalogue() {
  return useQuery({
    queryKey: [...queryKeys.team, "permissions"],
    queryFn: teamApi.permissions,
    staleTime: Infinity,
  });
}

export function useInviteMember() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role?: RoleNameApi }) => teamApi.invite(body),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.team }),
  });
}

export function useResendInvitation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => teamApi.resendInvitation(id),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.team }),
  });
}

export function useRevokeInvitation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => teamApi.revokeInvitation(id),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.team }),
  });
}

export function useUpdateMemberRole() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: RoleNameApi }) =>
      teamApi.updateMemberRole(userId, role),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.team }),
  });
}

export function useRemoveMember() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => teamApi.removeMember(userId),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.team }),
  });
}

// --- Map ----------------------------------------------------------------

/**
 * Leads within `radiusKm` of a point. Runs server-side (haversine over the
 * organization's own coordinates), replacing the client-side distance maths the
 * page used against fixtures.
 */
export function useNearbyLeads(
  params: { lat: number; lng: number; radius_km?: number; industry?: string } | null,
) {
  return useQuery({
    queryKey: [...queryKeys.map, "nearby", params],
    enabled: !!params,
    queryFn: async () => (await mapApi.nearbyLeads(params!)).map(toNearbyLead),
    placeholderData: (previous) => previous,
  });
}

export function useGeocode() {
  return useMutation({ mutationFn: (address: string) => mapApi.geocode(address) });
}

// --- Map Mode -------------------------------------------------------------

/**
 * Extracts public map results for review.
 *
 * A mutation rather than a query: it is an explicit user action with a cost in
 * time, and caching it by keyword would hide the fact that OSM data changes.
 */
export function useExtractMapResults() {
  return useMutation({
    mutationFn: (body: {
      query: string;
      location?: string;
      radius_km?: number;
      max_results?: number;
      source?: MapSource;
      extra_keywords?: string[];
      viewport?: MapViewport;
    }) => searchApi.extractMapResults(body),
  });
}

/** Imports the selected map results, then refreshes everything they affect. */
export function useImportMapResults() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (results: MapResult[]) => searchApi.importMapResults(results),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.leads });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
      client.invalidateQueries({ queryKey: queryKeys.analytics });
    },
  });
}

/** Runs contact enrichment, then refreshes everything it can change. */
export function useEnrichLeads() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { lead_ids?: string[]; all_unenriched?: boolean; limit?: number }) =>
      enrichmentApi.enrich(body),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.leads });
      client.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}
