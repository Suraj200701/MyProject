import type { ApiProvider } from "@/lib/types";

/**
 * Provider helpers, containing only what the backend can actually support.
 *
 * This replaces `mock-extras.ts`, which fabricated five different things from a
 * PRNG seeded on the provider id:
 *
 *   * `getSparklineData` — 7 days of usage volume. There is no per-provider time
 *     series on the backend (`ApiProvider` stores one cumulative `usage_count`),
 *     so a usage *history* cannot be shown at all.
 *   * `getUptimePercent` — an uptime figure biased by current status. Nothing
 *     records uptime.
 *   * `getTrend` — a 24h trend arrow. Nothing records history to trend against.
 *   * `getMaskedApiKey` — a plausible-looking `sk_live_…` string. Provider
 *     credentials are stored encrypted (`ApiProvider.api_key_encrypted`) and are
 *     deliberately never returned by any endpoint.
 *   * `getMockResponse` — a category-flavoured JSON payload for "Test
 *     Connection". There is no test-connection endpoint.
 *
 * What remains below is derived from real fields.
 */

/** Category tabs. Matches the backend's `ProviderCategory` enum plus an "All" option. */
export const CATEGORY_TABS = ["All", "Search", "Maps", "Business", "CRM", "AI"] as const;
export type CategoryTab = (typeof CATEGORY_TABS)[number];

export function categoryTabLabel(tab: CategoryTab): string {
  return tab === "All" ? "All Providers" : tab;
}

/** Quota consumption, from real `usage`/`limit` values. 0 when no quota is set. */
export function usagePercent(provider: ApiProvider): number {
  if (provider.limit <= 0) return 0;
  return Math.min(100, Math.round((provider.usage / provider.limit) * 100));
}

/** Remaining quota, floored at zero. */
export function remainingQuota(provider: ApiProvider): number {
  return Math.max(0, provider.limit - provider.usage);
}

/** True when the provider is close enough to its quota to warn about. */
export function isNearQuota(provider: ApiProvider): boolean {
  return usagePercent(provider) >= 90;
}

/**
 * Latency, described rather than scored.
 *
 * `latency_ms` is the real measured latency of the last call the backend made to
 * this provider — 0 means it has never been called, which is different from
 * "0ms" and is labelled as such.
 */
export function latencyLabel(provider: ApiProvider): string {
  if (provider.latencyMs <= 0) return "No traffic yet";
  return `${provider.latencyMs.toLocaleString()}ms last call`;
}
