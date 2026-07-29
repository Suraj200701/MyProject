"use client";

import { Building2, DollarSign, Plug, Store } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { mockLeads } from "@/lib/mock-data";

function topBy<T extends string>(items: T[]): { value: T; count: number } | null {
  const counts = new Map<T, number>();
  for (const item of items) counts.set(item, (counts.get(item) ?? 0) + 1);
  let best: { value: T; count: number } | null = null;
  for (const [value, count] of counts) {
    if (!best || count > best.count) best = { value, count };
  }
  return best;
}

function parseRevenueM(revenue: string): number {
  const n = parseFloat(revenue.replace(/[^0-9.]/g, ""));
  return Number.isFinite(n) ? n : 0;
}

export function BusinessAnalyticsCard() {
  const topCompanyType = topBy(mockLeads.map((l) => l.companyType));
  const topProvider = topBy(mockLeads.map((l) => l.provider));
  const avgRevenue = mockLeads.reduce((sum, l) => sum + parseRevenueM(l.revenue), 0) / mockLeads.length;

  const stats = [
    { icon: Building2, label: "Top Company Type", value: topCompanyType?.value ?? "—", hint: `${topCompanyType?.count ?? 0} leads` },
    { icon: Plug, label: "Top Sourcing Provider", value: topProvider?.value ?? "—", hint: `${topProvider?.count ?? 0} leads` },
    { icon: DollarSign, label: "Avg Revenue Band", value: `$${avgRevenue.toFixed(1)}M`, hint: "across all leads" },
    { icon: Store, label: "Total Companies Tracked", value: mockLeads.length.toLocaleString(), hint: "unique leads" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Business Analytics</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {stats.map((s) => (
          <div key={s.label} className="flex items-center gap-3 rounded-lg border border-border bg-surface-2/40 px-3 py-2.5">
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
      </CardContent>
    </Card>
  );
}
