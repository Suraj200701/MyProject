"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiProviders, mockLeads } from "@/lib/mock-data";
import type { ApiProvider } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_VARIANT: Record<ApiProvider["status"], "success" | "warning" | "danger"> = {
  healthy: "success",
  degraded: "warning",
  down: "danger",
};

// Providers whose name is directly attributable to a Lead["provider"] value in mock-data.
const SOURCING_KEYS = ["Google Places", "Mappls", "IndiaMART", "TradeIndia", "JustDial", "LinkedIn"];

function leadsContributedFor(provider: ApiProvider, sourcingCounts: Map<string, number>): number {
  const matchKey = SOURCING_KEYS.find((key) => provider.name.includes(key));
  if (matchKey) return sourcingCounts.get(matchKey) ?? 0;
  // Non-sourcing providers (AI enrichment, email discovery, etc.) contribute indirectly.
  return Math.round(provider.usage * 0.04);
}

export function ProviderPerformanceCard() {
  const sourcingCounts = new Map<string, number>();
  for (const lead of mockLeads) {
    sourcingCounts.set(lead.provider, (sourcingCounts.get(lead.provider) ?? 0) + 1);
  }

  const ranked = [...apiProviders]
    .map((provider) => ({
      provider,
      leadsContributed: leadsContributedFor(provider, sourcingCounts),
      usagePct: provider.limit > 0 ? (provider.usage / provider.limit) * 100 : 0,
    }))
    .sort((a, b) => b.leadsContributed - a.leadsContributed);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Provider Performance</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Ranked by leads contributed this period</p>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Provider</th>
                <th className="py-2 pr-3 font-medium">Category</th>
                <th className="py-2 pr-3 font-medium text-right">Usage</th>
                <th className="py-2 pr-3 font-medium text-right">Leads contributed</th>
                <th className="py-2 pl-3 font-medium text-right">Status</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map(({ provider, leadsContributed, usagePct }) => (
                <tr key={provider.id} className="border-b border-border/60 last:border-0">
                  <td className="py-2.5 pr-3">
                    <div className="flex items-center gap-2">
                      <span className="text-base leading-none">{provider.logo}</span>
                      <span className="font-medium text-foreground">{provider.name}</span>
                    </div>
                  </td>
                  <td className="py-2.5 pr-3 text-muted-foreground">{provider.category}</td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">
                    <span className="text-foreground">{provider.usage.toLocaleString()}</span>
                    <span className="text-muted-foreground"> / {provider.limit.toLocaleString()}</span>
                    <div
                      className={cn(
                        "ml-auto mt-1 h-1 w-16 overflow-hidden rounded-full bg-surface-2",
                      )}
                    >
                      <div
                        className="h-full rounded-full bg-[linear-gradient(90deg,var(--color-primary),var(--color-accent))]"
                        style={{ width: `${Math.min(usagePct, 100)}%` }}
                      />
                    </div>
                  </td>
                  <td className="py-2.5 pr-3 text-right font-medium tabular-nums text-foreground">
                    {leadsContributed.toLocaleString()}
                  </td>
                  <td className="py-2.5 pl-3 text-right">
                    <Badge variant={STATUS_VARIANT[provider.status]} className="capitalize">
                      {provider.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
