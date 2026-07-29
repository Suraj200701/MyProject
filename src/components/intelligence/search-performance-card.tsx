"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { searchAnalytics } from "@/lib/mock-data";
import { ChartTooltip } from "./chart-tooltip";

export function SearchPerformanceCard() {
  const totalSearches = searchAnalytics.reduce((sum, d) => sum + d.searches, 0);
  const avgPerDay = totalSearches / searchAnalytics.length;
  const bestDay = searchAnalytics.reduce((best, d) => (d.searches > best.searches ? d : best), searchAnalytics[0]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Search Performance</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Search volume over the last 7 days</p>
      </CardHeader>
      <CardContent className="pt-4">
        <div className="mb-4 flex flex-wrap gap-2">
          <div className="rounded-lg border border-border bg-surface-2/60 px-3 py-2">
            <p className="text-xs text-muted-foreground">Avg. searches / day</p>
            <p className="text-sm font-semibold tabular-nums">{avgPerDay.toFixed(1)}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/60 px-3 py-2">
            <p className="text-xs text-muted-foreground">Best day</p>
            <p className="text-sm font-semibold tabular-nums">
              {bestDay.day} &middot; {bestDay.searches}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/60 px-3 py-2">
            <p className="text-xs text-muted-foreground">Total this week</p>
            <p className="text-sm font-semibold tabular-nums">{totalSearches}</p>
          </div>
        </div>
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={searchAnalytics} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis
                dataKey="day"
                stroke="var(--color-border)"
                tick={{ fill: "var(--color-muted-foreground)", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="var(--color-border)"
                tick={{ fill: "var(--color-muted-foreground)", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--color-surface-2)" }} />
              <Bar dataKey="searches" name="Searches" fill="var(--color-primary)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
