"use client";

import { Building2, Gauge, Plug, Store } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AsyncContent, SkeletonRows } from "@/components/shared/async-content";
import { useBusinessSummary, useDashboardStats } from "@/lib/api/queries";

/**
 * Headline business figures, all from `GET /analytics/business-summary`.
 *
 * One tile changed meaning. The previous "Avg Revenue Band" parsed a dollar
 * figure out of each lead's revenue *band* string ("$1M-$5M") and averaged the
 * result — arithmetic on a label, producing a number that meant nothing. The
 * backend exposes no average-revenue metric, so that tile is now "Avg Lead
 * Score", which is a real figure from the dashboard stats endpoint.
 */
export function BusinessAnalyticsCard() {
  const { data: summary, isPending, isError, error } = useBusinessSummary();
  const { data: stats } = useDashboardStats();

  const tiles = summary
    ? [
        {
          icon: Building2,
          label: "Top Company Type",
          value: summary.top_company_type ?? "—",
          hint: `${summary.top_company_type_count.toLocaleString()} leads`,
        },
        {
          icon: Plug,
          label: "Top Sourcing Provider",
          value: summary.top_provider_name ?? "—",
          hint: `${summary.top_provider_lead_count.toLocaleString()} leads`,
        },
        {
          icon: Gauge,
          label: "Avg Lead Score",
          value: stats ? `${stats.avgLeadScore}` : "—",
          hint: "across all leads",
        },
        {
          icon: Store,
          label: "Total Companies Tracked",
          value: summary.total_companies.toLocaleString(),
          hint: "unique companies",
        },
      ]
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Business Analytics</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <AsyncContent
          isPending={isPending}
          isError={isError}
          error={error}
          className="col-span-full min-h-[140px]"
          skeleton={<SkeletonRows rows={2} />}
        >
          {tiles.map((s) => (
            <div
              key={s.label}
              className="flex items-center gap-3 rounded-lg border border-border bg-surface-2/40 px-3 py-2.5"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
                <s.icon className="size-4 text-muted-foreground" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">{s.value}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {s.label} · {s.hint}
                </p>
              </div>
            </div>
          ))}
        </AsyncContent>
      </CardContent>
    </Card>
  );
}
