"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useApiUsage } from "@/lib/api/queries";
import { AsyncContent } from "@/components/shared/async-content";

export function ApiUsageChart() {
  const { data, isPending, isError, error } = useApiUsage();
  const apiUsageData = data ?? [];
  return (
    <Card className="glass overflow-hidden">
      <CardHeader>
        <CardTitle>API Usage</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Consumption against monthly provider limits</p>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={apiUsageData.length === 0}
        emptyMessage="No provider usage recorded yet."
        className="min-h-[200px] p-5"
      >
      <div className="flex flex-col gap-4 p-5">
        {apiUsageData.map((item) => {
          const pct = Math.min(100, Math.round((item.usage / item.limit) * 100));
          const critical = pct >= 90;
          return (
            <div key={item.name} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="truncate text-foreground/90">{item.name}</span>
                <span className="shrink-0 tabular-nums text-xs text-muted-foreground">
                  {item.usage.toLocaleString()} / {item.limit.toLocaleString()}
                </span>
              </div>
              <Progress
                value={pct}
                indicatorClassName={critical ? "bg-[linear-gradient(90deg,var(--color-warning),var(--color-danger))]" : undefined}
              />
            </div>
          );
        })}
      </div>
      </AsyncContent>
    </Card>
  );
}
