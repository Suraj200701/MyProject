"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { industryDistribution } from "@/lib/mock-data";
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
  const total = industryDistribution.reduce((sum, d) => sum + d.value, 0);

  return (
    <Card className="glass overflow-hidden">
      <CardHeader>
        <CardTitle>Industry Distribution</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Share of leads by industry vertical</p>
      </CardHeader>
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
        <div className="flex w-full flex-col gap-2.5">
          {industryDistribution.map((entry, i) => (
            <div key={entry.name} className="flex items-center gap-2.5 text-sm">
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: COLORS[i % COLORS.length] }}
              />
              <span className="truncate text-foreground/90">{entry.name}</span>
              <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">
                {Math.round((entry.value / total) * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
