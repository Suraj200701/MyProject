"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLeadGrowth } from "@/lib/api/queries";
import { AsyncContent } from "@/components/shared/async-content";
import { ChartTooltip } from "./chart-tooltip";

export function LeadTrendsChart() {
  const { data, isPending, isError, error } = useLeadGrowth();
  const leadGrowthData = data ?? [];
  const first = leadGrowthData[0]?.leads ?? 0;
  const last = leadGrowthData[leadGrowthData.length - 1]?.leads ?? 0;
  const delta = first > 0 ? ((last - first) / first) * 100 : 0;
  const positive = delta >= 0;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2">
        <div>
          <CardTitle>Lead Trends</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">Leads captured vs. converted, by month</p>
        </div>
        <Badge variant={positive ? "success" : "danger"}>
          {positive ? "+" : ""}
          {delta.toFixed(0)}% vs last period
        </Badge>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={leadGrowthData.length === 0}
        emptyMessage="No trend data yet."
        className="h-72 p-6"
      >
      <CardContent className="pt-4">
        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={leadGrowthData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="leadsGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="convertedGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis
                dataKey="month"
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
              <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--color-border-strong)", strokeWidth: 1 }} />
              <Area
                type="monotone"
                dataKey="leads"
                name="Leads"
                stroke="var(--color-primary)"
                strokeWidth={2}
                fill="url(#leadsGradient)"
              />
              <Area
                type="monotone"
                dataKey="converted"
                name="Converted"
                stroke="var(--color-accent)"
                strokeWidth={2}
                fill="url(#convertedGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
      </AsyncContent>
    </Card>
  );
}
