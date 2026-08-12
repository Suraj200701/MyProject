"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { useIndustryDistribution } from "@/lib/api/queries";
import { AsyncContent } from "@/components/shared/async-content";
import { ChartTooltip } from "@/components/dashboard/chart-tooltip";

const COLORS = [
  "var(--color-primary)",
  "var(--color-accent)",
  "var(--color-success)",
  "var(--color-warning)",
  "oklch(0.7 0.19 330)",
  "oklch(0.72 0.15 40)",
];

export function IndustryDistributionChart() {
  const { data, isPending, isError, error } = useIndustryDistribution();
  const industryDistribution = data ?? [];
  const total = industryDistribution.reduce((sum, d) => sum + d.value, 0);

  return (
    <Card className="glass overflow-hidden">
      <CardHeader>
        <CardTitle>Industry Distribution</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Share of leads by industry vertical</p>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={industryDistribution.length === 0}
        emptyMessage="No industry data yet — run a search to populate this."
        className="h-[264px] p-5"
      >
      <div className="flex flex-col items-center gap-4 p-5 sm:flex-row">
        <div className="h-56 w-full max-w-[220px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={industryDistribution}
                dataKey="value"
                nameKey="name"
                innerRadius="62%"
                outerRadius="100%"
                paddingAngle={2}
                stroke="var(--color-card)"
                strokeWidth={2}
              >
                {industryDistribution.map((entry, i) => (
                  <Cell key={entry.name} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        {/* `min-w-0 flex-1`, not `w-full`. As a flex item this defaults to
            `min-width: auto`, so it refuses to shrink below its content and
            overflows the card — which has `overflow: hidden`, so the industry
            labels were simply clipped off the right edge. Measured at a 1280px
            viewport (a 1920px laptop at the usual 150% scaling): the legend ran
            87px past the card. It also means the `truncate` below can finally
            engage, since truncation needs an ancestor that is allowed to shrink. */}
        <div className="flex min-w-0 flex-1 flex-col gap-2.5">
          {industryDistribution.map((entry, i) => (
            <div key={entry.name} className="flex items-center gap-2.5 text-sm">
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              <span className="truncate text-foreground/90">{entry.name}</span>
              <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">
                {/* Guarded: a dataset whose values are all zero passes the
                    non-empty check above but makes `total` 0, rendering "NaN%". */}
                {total > 0 ? Math.round((entry.value / total) * 100) : 0}%
              </span>
            </div>
          ))}
        </div>
      </div>
      </AsyncContent>
    </Card>
  );
}
