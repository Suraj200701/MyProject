import { Activity, AlertTriangle, Gauge, Plug } from "lucide-react";
import { StatCard } from "@/components/shared/stat-card";
import type { ApiProvider } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

export function StatsRow({ providers }: { providers: ApiProvider[] }) {
  const connected = providers.filter((p) => p.connected).length;
  const requestsToday = providers.reduce((sum, p) => sum + p.usage, 0);
  const activeLatencies = providers.filter((p) => p.latencyMs > 0);
  const avgLatency = activeLatencies.length
    ? Math.round(activeLatencies.reduce((sum, p) => sum + p.latencyMs, 0) / activeLatencies.length)
    : 0;
  const issues = providers.filter((p) => p.status === "degraded" || p.status === "down").length;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        label="Connected Providers"
        value={`${connected} / ${providers.length}`}
        icon={Plug}
        accent="primary"
      />
      <StatCard
        label="Requests Today"
        value={formatNumber(requestsToday)}
        icon={Activity}
        accent="accent"
      />
      <StatCard
        label="Avg Latency"
        value={`${avgLatency} ms`}
        icon={Gauge}
        accent="success"
      />
      <StatCard
        label="Providers With Issues"
        value={String(issues)}
        icon={AlertTriangle}
        accent="warning"
      />
    </div>
  );
}
