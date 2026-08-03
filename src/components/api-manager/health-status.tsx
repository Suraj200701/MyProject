import type { ApiProvider } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusPill } from "@/components/api-manager/status-pill";
import { latencyLabel, remainingQuota } from "@/components/api-manager/provider-utils";

/**
 * Provider health, from real fields only.
 *
 * The uptime percentage and 24h trend arrow that used to sit on the right of each
 * row are gone: both were generated from a PRNG seeded on the provider id (see
 * the note in `provider-utils.ts`). The backend records neither uptime nor any
 * history to trend against. Remaining quota replaces them — a real figure from
 * `usage_count`/`usage_limit` that is genuinely useful in this position.
 */
export function HealthStatus({ providers }: { providers: ApiProvider[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Health Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {providers.length === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-muted-foreground">
            No providers configured.
          </p>
        ) : (
          providers.map((provider) => (
            <div
              key={provider.id}
              className="flex items-center justify-between rounded-lg px-2 py-2.5 hover:bg-surface-2/50 transition-colors"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="text-base">{provider.logo}</span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{provider.name}</p>
                  <p className="text-xs text-muted-foreground">{latencyLabel(provider)}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs tabular-nums text-muted-foreground">
                  {provider.limit > 0
                    ? `${remainingQuota(provider).toLocaleString()} left`
                    : "No quota set"}
                </span>
                <StatusPill status={provider.status} />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
