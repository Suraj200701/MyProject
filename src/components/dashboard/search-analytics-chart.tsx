"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { searchAnalytics } from "@/lib/mock-data";
import { ChartTooltip } from "@/components/dashboard/chart-tooltip";

export function SearchAnalyticsChart() {
  return (
    <Card className="glass overflow-hidden">
      <CardHeader>
        <CardTitle>Search Analytics</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Searches run this week</p>
      </CardHeader>
      <div className="h-64 w-full px-2 pb-4 pt-4 sm:px-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={searchAnalytics} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
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
              width={32}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--color-surface-2)" }} />
            <Bar dataKey="searches" name="Searches" fill="var(--color-primary)" radius={[6, 6, 0, 0]} maxBarSize={36} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
