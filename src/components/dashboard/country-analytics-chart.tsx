"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { countryAnalytics } from "@/lib/mock-data";

const flags: Record<string, string> = {
  India: "🇮🇳",
  UAE: "🇦🇪",
  Singapore: "🇸🇬",
  "United States": "🇺🇸",
  "United Kingdom": "🇬🇧",
  Indonesia: "🇮🇩",
};

export function CountryAnalyticsChart() {
  const max = Math.max(...countryAnalytics.map((c) => c.leads));

  return (
    <Card className="glass overflow-hidden">
      <CardHeader>
        <CardTitle>Leads by Country</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Geographic distribution of your lead base</p>
      </CardHeader>
      <div className="flex flex-col gap-4 p-5">
        {countryAnalytics.map((item) => (
          <div key={item.country} className="flex items-center gap-3">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-md border border-border bg-surface-2 text-sm">
              {flags[item.country] ?? item.country.slice(0, 2).toUpperCase()}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="truncate text-foreground/90">{item.country}</span>
                <span className="shrink-0 tabular-nums text-xs text-muted-foreground">
                  {item.leads.toLocaleString()}
                </span>
              </div>
              <Progress value={(item.leads / max) * 100} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
