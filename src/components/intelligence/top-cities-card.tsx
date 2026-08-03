"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { AsyncContent, SkeletonRows } from "@/components/shared/async-content";
import { useTopCities } from "@/lib/api/queries";

export function TopCitiesCard() {
  // Aggregated and ranked in SQL by GET /analytics/top-cities, rather than
  // counted client-side over whatever leads happened to be loaded.
  const { data, isPending, isError, error } = useTopCities();
  const cities = data ?? [];
  const max = cities.length > 0 ? Math.max(...cities.map((c) => c.leads)) : 1;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top Cities</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <AsyncContent
          isPending={isPending}
          isError={isError}
          error={error}
          isEmpty={cities.length === 0}
          emptyMessage="No city data yet."
          className="min-h-[200px]"
          skeleton={<SkeletonRows rows={5} />}
        >
          {cities.map((c) => {
            const pct = max > 0 ? (c.leads / max) * 100 : 0;
            return (
              <div key={`${c.city}-${c.country ?? ""}`}>
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="font-medium text-foreground">
                    {c.city}
                    {c.country ? (
                      <span className="ml-1.5 text-xs text-muted-foreground">{c.country}</span>
                    ) : null}
                  </span>
                  <span className="text-muted-foreground tabular-nums">{c.leads} leads</span>
                </div>
                <Progress value={pct} />
              </div>
            );
          })}
        </AsyncContent>
      </CardContent>
    </Card>
  );
}
