"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AsyncContent } from "@/components/shared/async-content";
import { useExportAnalytics } from "@/lib/api/queries";

interface TooltipPayloadEntry {
  dataKey?: string | number;
  name?: string | number;
  color?: string;
  value?: number | string;
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayloadEntry[]; label?: string | number }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-lg border border-border-strong bg-popover p-2.5 text-xs shadow-xl">
      <p className="mb-1.5 font-medium text-popover-foreground">{label}</p>
      <div className="flex flex-col gap-1">
        {payload.map((entry, i) => (
          <div key={entry.dataKey ?? i} className="flex items-center gap-2">
            <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-muted-foreground">{entry.name}</span>
            <span className="ml-auto font-medium text-popover-foreground">{entry.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ExportAnalyticsChart() {
  const { data, isPending, isError, error } = useExportAnalytics();
  const exportAnalytics = data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Export Analytics</CardTitle>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={exportAnalytics.length === 0}
        emptyMessage="No exports yet — generate one to populate this."
        className="h-72 p-6"
      >
        <CardContent className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={exportAnalytics}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--color-surface-2)" }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="csv" name="CSV" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="excel" name="Excel" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="pdf" name="PDF" fill="var(--color-success)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </AsyncContent>
    </Card>
  );
}
