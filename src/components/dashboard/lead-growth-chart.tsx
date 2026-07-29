"use client";

import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { leadGrowthData } from "@/lib/mock-data";
import { ChartTooltip } from "@/components/dashboard/chart-tooltip";

const periods = ["6M", "3M", "1M"] as const;

export function LeadGrowthChart() {
  const [period, setPeriod] = useState<(typeof periods)[number]>("6M");

  const data =
    period === "3M" ? leadGrowthData.slice(-3) : period === "1M" ? leadGrowthData.slice(-1) : leadGrowthData;

  return (
    <Card className="glass overflow-hidden">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>Lead Growth</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">New vs. converted leads over time</p>
        </div>
        <Tabs value={period} onValueChange={(v) => setPeriod(v as (typeof periods)[number])}>
          <TabsList>
            {periods.map((p) => (
              <TabsTrigger key={p} value={p} className="px-2.5 text-xs">
                {p}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </CardHeader>
      <div className="h-72 w-full px-2 pb-4 pt-4 sm:px-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="leadsFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.35} />
                <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="convertedFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.35} />
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
              width={40}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--color-border-strong)", strokeWidth: 1 }} />
            <Area
              type="monotone"
              dataKey="leads"
              name="Total Leads"
              stroke="var(--color-primary)"
              strokeWidth={2}
              fill="url(#leadsFill)"
            />
            <Area
              type="monotone"
              dataKey="converted"
              name="Converted"
              stroke="var(--color-accent)"
              strokeWidth={2}
              fill="url(#convertedFill)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
