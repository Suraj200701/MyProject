"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { industryDistribution } from "@/lib/mock-data";

const BAR_COLORS = [
  "bg-[linear-gradient(90deg,var(--color-primary),var(--color-accent))]",
  "bg-[linear-gradient(90deg,var(--color-accent),var(--color-primary))]",
];

export function TopIndustriesCard() {
  const total = industryDistribution.reduce((sum, i) => sum + i.value, 0);
  const sorted = [...industryDistribution].sort((a, b) => b.value - a.value);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top Industries</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {sorted.map((industry, i) => {
          const pct = total > 0 ? (industry.value / total) * 100 : 0;
          return (
            <div key={industry.name}>
              <div className="mb-1.5 flex items-center justify-between text-sm">
                <span className="font-medium text-foreground">{industry.name}</span>
                <span className="text-muted-foreground tabular-nums">{pct.toFixed(1)}%</span>
              </div>
              <Progress
                value={pct}
                indicatorClassName={BAR_COLORS[i % BAR_COLORS.length]}
              />
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
