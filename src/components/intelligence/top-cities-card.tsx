"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { mockLeads } from "@/lib/mock-data";

export function TopCitiesCard() {
  const counts = new Map<string, { city: string; country: string; count: number }>();
  for (const lead of mockLeads) {
    const existing = counts.get(lead.city);
    if (existing) {
      existing.count += 1;
    } else {
      counts.set(lead.city, { city: lead.city, country: lead.country, count: 1 });
    }
  }

  const cities = Array.from(counts.values())
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  const max = cities.length > 0 ? cities[0].count : 1;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top Cities</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {cities.map((c) => {
          const pct = (c.count / max) * 100;
          return (
            <div key={c.city}>
              <div className="mb-1.5 flex items-center justify-between text-sm">
                <span className="font-medium text-foreground">
                  {c.city}
                  <span className="ml-1.5 text-xs text-muted-foreground">{c.country}</span>
                </span>
                <span className="text-muted-foreground tabular-nums">{c.count} leads</span>
              </div>
              <Progress value={pct} />
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
