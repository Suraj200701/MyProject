import { Plug } from "lucide-react";
import Link from "next/link";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { apiProviders } from "@/lib/mock-data";
import type { ApiProvider } from "@/lib/types";

const statusColor: Record<ApiProvider["status"], string> = {
  healthy: "bg-success",
  degraded: "bg-warning",
  down: "bg-danger",
};

const statusLabel: Record<ApiProvider["status"], string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  down: "Down",
};

export function ProviderHealth() {
  return (
    <Card className="glass overflow-hidden">
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <div className="flex size-7 items-center justify-center rounded-lg bg-surface-2 text-foreground/80">
          <Plug className="size-3.5" />
        </div>
        <CardTitle>Provider Health</CardTitle>
      </CardHeader>
      <div className="grid grid-cols-1 gap-2 p-5 pt-3 sm:grid-cols-2">
        {apiProviders.map((provider) => (
          <div
            key={provider.id}
            className="flex items-center gap-2.5 rounded-lg border border-border bg-surface-2/50 px-3 py-2.5"
          >
            <span className="text-base leading-none">{provider.logo}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-foreground/90">{provider.name}</p>
              <p className="text-[11px] text-muted-foreground">
                {provider.status === "down" ? "Offline" : `${provider.latencyMs}ms latency`}
              </p>
            </div>
            <span className="flex shrink-0 items-center gap-1.5">
              <span className={cn("size-1.5 rounded-full", statusColor[provider.status])} />
              <span className="text-[11px] text-muted-foreground">{statusLabel[provider.status]}</span>
            </span>
          </div>
        ))}
      </div>
      <div className="border-t border-border px-5 py-3">
        <Link href="/dashboard/api-manager" className="text-xs font-medium text-primary hover:underline">
          Manage providers
        </Link>
      </div>
    </Card>
  );
}
