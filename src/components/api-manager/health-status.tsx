import { TrendingDown, TrendingUp, Minus } from "lucide-react";
import type { ApiProvider } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusPill } from "@/components/api-manager/status-pill";
import { getTrend, getUptimePercent } from "@/components/api-manager/mock-extras";
import { cn } from "@/lib/utils";

const TREND_ICON = { up: TrendingUp, down: TrendingDown, flat: Minus } as const;
const TREND_COLOR = { up: "text-success", down: "text-danger", flat: "text-muted-foreground" } as const;

export function HealthStatus({ providers }: { providers: ApiProvider[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Health Status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {providers.map((provider) => {
          const uptime = getUptimePercent(provider);
          const trend = getTrend(provider);
          const TrendIcon = TREND_ICON[trend];
          return (
            <div
              key={provider.id}
              className="flex items-center justify-between rounded-lg px-2 py-2.5 hover:bg-surface-2/50 transition-colors"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="text-base">{provider.logo}</span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{provider.name}</p>
                  <p className="text-xs text-muted-foreground">{provider.latencyMs > 0 ? `${provider.latencyMs}ms latency` : "No traffic"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs tabular-nums text-muted-foreground">{uptime}% uptime</span>
                <TrendIcon className={cn("size-3.5", TREND_COLOR[trend])} />
                <StatusPill status={provider.status} />
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
