/**
 * Wire format -> view model.
 *
 * The backend speaks snake_case and allows nulls almost everywhere; the existing
 * components consume camelCase view types (`src/lib/types.ts`) with
 * non-nullable fields, because they were written against fixtures. Rather than
 * touch ~60 components to handle `string | null` — which would mean redesigning
 * them — every response is normalized here.
 *
 * Two rules this file follows:
 *
 * 1. **Null becomes empty, never fabricated.** A missing email becomes `""` so
 *    `lead.email.toLowerCase()` in a filter doesn't crash, and the UI's existing
 *    falsy checks render its em-dash placeholder. Nothing is invented to fill a
 *    gap — that was the whole point of removing the mock generators.
 *
 * 2. **Field names are the only thing that changes.** No values are reshaped,
 *    rounded or relabelled, so what the UI shows is what the API returned.
 */

import type {
  ApiProvider as ApiProviderView,
  Lead as LeadView,
  NotificationItem as NotificationView,
  SearchHistoryItem as SearchHistoryView,
} from "@/lib/types";
import type {
  ApiProviderOut,
  DashboardStatsOut,
  LeadOut,
  NearbyLeadOut,
  NotificationOut,
  SearchOut,
} from "@/lib/api/types";

/** `null`/`undefined` -> `""`. Keeps the view types non-nullable. */
const str = (value: string | null | undefined): string => value ?? "";

/** `null`/`undefined` -> `0`. For numeric fields the UI renders or sorts on. */
const num = (value: number | null | undefined): number => value ?? 0;

// --- Leads ---------------------------------------------------------------

/**
 * `LeadOut` -> the `Lead` shape every leads component already consumes.
 *
 * `revenue_band` -> `revenue` and `gst_number` -> `gst` are the only two
 * renames that aren't a straight snake->camel conversion; both match the names
 * the existing table columns and profile fields read.
 */
export function toLead(dto: LeadOut): LeadView {
  return {
    id: dto.id,
    company: str(dto.company),
    industry: str(dto.industry),
    city: str(dto.city),
    country: str(dto.country),
    contactName: str(dto.contact_name),
    email: str(dto.email),
    phone: str(dto.phone),
    website: str(dto.website),
    rating: num(dto.rating),
    revenue: str(dto.revenue_band),
    leadScore: num(dto.lead_score),
    status: dto.status,
    companyType: str(dto.company_type),
    provider: str(dto.provider),
    tags: dto.tags ?? [],
    createdAt: dto.created_at,
    gst: dto.gst_number ?? undefined,
    // 0/0 is in the Gulf of Guinea, so a lead with no coordinates would render
    // as a pin off the African coast. NaN keeps it out of the map's projection
    // and out of its bounds calculation instead of placing it somewhere false.
    lat: dto.lat ?? Number.NaN,
    lng: dto.lng ?? Number.NaN,
    aiSummary: str(dto.ai_summary),
  };
}

export const toLeads = (dtos: LeadOut[]): LeadView[] => dtos.map(toLead);

/** True when a lead can actually be placed on the map. */
export const hasCoordinates = (lead: LeadView): boolean =>
  Number.isFinite(lead.lat) && Number.isFinite(lead.lng);

/**
 * `NearbyLeadOut` -> a partial `Lead`.
 *
 * The nearby-leads endpoint returns a deliberately narrow projection (it is a
 * geospatial query, not a lead fetch), so the fields it doesn't carry are left
 * empty rather than defaulted to something plausible. `distanceKm` is carried
 * alongside because the map list renders it.
 */
export function toNearbyLead(dto: NearbyLeadOut): LeadView & { distanceKm: number } {
  return {
    id: dto.lead_id,
    company: str(dto.company_name),
    industry: str(dto.industry),
    city: str(dto.city),
    country: "",
    contactName: "",
    email: "",
    phone: "",
    website: "",
    rating: 0,
    revenue: "",
    leadScore: num(dto.lead_score),
    status: "new",
    companyType: "",
    provider: "",
    tags: [],
    createdAt: "",
    lat: dto.lat,
    lng: dto.lng,
    aiSummary: "",
    distanceKm: dto.distance_km,
  };
}

// --- Providers -----------------------------------------------------------

/**
 * `ApiProviderOut` -> `ApiProvider`.
 *
 * `category` and `status` need no translation: the backend's enums are already
 * Title-case ("Maps") and lowercase ("healthy") respectively, matching the
 * frontend unions exactly.
 */
export function toApiProvider(dto: ApiProviderOut): ApiProviderView {
  return {
    id: dto.id,
    name: dto.name,
    category: dto.category,
    status: dto.status,
    usage: num(dto.usage_count),
    limit: num(dto.usage_limit),
    latencyMs: num(dto.latency_ms),
    // The UI renders this emoji in a fixed-size chip; a generic plug avoids an
    // empty box when a provider row has no logo set.
    logo: str(dto.logo) || "🔌",
    description: str(dto.description),
    connected: dto.connected,
  };
}

export const toApiProviders = (dtos: ApiProviderOut[]): ApiProviderView[] =>
  dtos.map(toApiProvider);

// --- Searches ------------------------------------------------------------

/** `SearchOut` -> `SearchHistoryItem`. `status` unions already align. */
export function toSearchHistoryItem(dto: SearchOut): SearchHistoryView {
  return {
    id: dto.id,
    query: dto.query,
    location: str(dto.location),
    results: num(dto.results_count),
    createdAt: dto.created_at,
    status: dto.status,
  };
}

export const toSearchHistory = (dtos: SearchOut[]): SearchHistoryView[] =>
  dtos.map(toSearchHistoryItem);

// --- Notifications -------------------------------------------------------

/** `NotificationOut` -> `NotificationItem`. Only `description` needs a fallback. */
export function toNotification(dto: NotificationOut): NotificationView {
  return {
    id: dto.id,
    title: dto.title,
    description: str(dto.description),
    type: dto.type,
    read: dto.read,
    createdAt: dto.created_at,
  };
}

export const toNotifications = (dtos: NotificationOut[]): NotificationView[] =>
  dtos.map(toNotification);

// --- Dashboard stats -----------------------------------------------------

/**
 * The camelCase stats object the dashboard, topbar, billing and settings
 * widgets already read. Same field names the removed `dashboardStats` fixture
 * exposed, so those components need no prop changes.
 */
export interface DashboardStatsView {
  totalLeads: number;
  todayLeads: number;
  conversionRate: number;
  avgLeadScore: number;
  searchCount: number;
  creditsRemaining: number;
  creditsTotal: number;
}

export function toDashboardStats(dto: DashboardStatsOut): DashboardStatsView {
  return {
    totalLeads: num(dto.total_leads),
    todayLeads: num(dto.today_leads),
    conversionRate: num(dto.conversion_rate),
    avgLeadScore: num(dto.avg_lead_score),
    searchCount: num(dto.search_count),
    creditsRemaining: num(dto.credits_remaining),
    creditsTotal: num(dto.credits_total),
  };
}

/** Zeroed stats, used as the placeholder while the real figures load. */
export const EMPTY_DASHBOARD_STATS: DashboardStatsView = {
  totalLeads: 0,
  todayLeads: 0,
  conversionRate: 0,
  avgLeadScore: 0,
  searchCount: 0,
  creditsRemaining: 0,
  creditsTotal: 0,
};

// --- Display helpers ----------------------------------------------------

/** Money from cents, e.g. 24900 -> "$249.00". */
export function formatCents(cents: number, currency = "USD"): string {
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);
  } catch {
    // Intl throws on an unrecognized currency code from the API.
    return `${(cents / 100).toFixed(2)} ${currency}`;
  }
}

/** Byte count -> "1.2 MB". Mirrors the backend's `size_label` convention. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

/** "owner" -> "Owner". Backend role/status enums are lowercase. */
export const titleCase = (value: string): string =>
  value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
