"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AsyncContent, SkeletonRows } from "@/components/shared/async-content";
import { useProviderPerformance, useProviders } from "@/lib/api/queries";
import { cn } from "@/lib/utils";

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger"> = {
  healthy: "success",
  degraded: "warning",
  down: "danger",
};

/**
 * Provider leaderboard, from `GET /analytics/provider-performance`.
 *
 * `leads_contributed` is now a real figure: the backend counts leads joined to
 * each provider. The previous version guessed it — sourcing providers were
 * matched by substring against a hardcoded name list, and every other provider
 * got `Math.round(usage * 0.04)`, an invented conversion rate presented in a
 * column headed "Leads contributed".
 *
 * The logo isn't part of the analytics payload, so it's looked up from the
 * provider catalogue by id.
 */
export function ProviderPerformanceCard() {
  const { data, isPending, isError, error } = useProviderPerformance();
  const { data: providers } = useProviders();

  const logoById = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const p of providers ?? []) map.set(p.id, p.logo);
    return map;
  }, [providers]);

  // Already ordered by leads contributed server-side; sorted here too so the
  // ranking is stable if that ever changes.
  const ranked = React.useMemo(
    () => [...(data ?? [])].sort((a, b) => b.leads_contributed - a.leads_contributed),
    [data],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Provider Performance</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Ranked by leads contributed</p>
      </CardHeader>
      <CardContent className="pt-2">
        <AsyncContent
          isPending={isPending}
          isError={isError}
          error={error}
          isEmpty={ranked.length === 0}
          emptyMessage="No provider activity yet."
          className="min-h-[200px]"
          skeleton={<SkeletonRows rows={5} />}
        >
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
                {ranked.map((row) => {
                  const usagePct = row.usage_limit > 0 ? (row.usage / row.usage_limit) * 100 : 0;
                  return (
                    <tr key={row.provider_id} className="border-b border-border/60 last:border-0">
                      <td className="py-2.5 pr-3">
                        <div className="flex items-center gap-2">
                          <span className="text-base leading-none">
                            {logoById.get(row.provider_id) ?? "🔌"}
                          </span>
                          <span className="font-medium text-foreground">{row.name}</span>
                        </div>
                      </td>
                      <td className="py-2.5 pr-3 text-muted-foreground">{row.category}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums">
                        <span className="text-foreground">{row.usage.toLocaleString()}</span>
                        <span className="text-muted-foreground"> / {row.usage_limit.toLocaleString()}</span>
                        <div className={cn("ml-auto mt-1 h-1 w-16 overflow-hidden rounded-full bg-surface-2")}>
                          <div
                            className="h-full rounded-full bg-[linear-gradient(90deg,var(--color-primary),var(--color-accent))]"
                            style={{ width: `${Math.min(usagePct, 100)}%` }}
                          />
                        </div>
                      </td>
                      <td className="py-2.5 pr-3 text-right font-medium tabular-nums text-foreground">
                        {row.leads_contributed.toLocaleString()}
                      </td>
                      <td className="py-2.5 pl-3 text-right">
                        <Badge variant={STATUS_VARIANT[row.status] ?? "warning"} className="capitalize">
                          {row.status}
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </AsyncContent>
      </CardContent>
    </Card>
  );
}
