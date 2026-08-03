"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSearchAnalytics } from "@/lib/api/queries";
import { AsyncContent } from "@/components/shared/async-content";
import { ChartTooltip } from "./chart-tooltip";

export function SearchPerformanceCard() {
  const { data, isPending, isError, error } = useSearchAnalytics();
  const searchAnalytics = data ?? [];

  /**
   * Derived stats, computed defensively.
   *
   * `AsyncContent` guards the *markup* below, but these run during render
   * regardless — so on a brand-new account with no search history the previous
   * code crashed here before the empty state could ever render:
   *
   *   * `reduce(fn, searchAnalytics[0])` seeded from `[0]` of an empty array,
   *     returning `undefined`, and `bestDay.day` then threw
   *     "Cannot read properties of undefined (reading 'day')".
   *   * `totalSearches / searchAnalytics.length` was `0 / 0` -> `NaN`, which
   *     would have rendered as "NaN" in the average tile.
   *
   * Seeding the reduce with a neutral value and guarding the division fixes both
   * at the source, rather than moving the guard around.
   */
  const totalSearches = searchAnalytics.reduce((sum, d) => sum + d.searches, 0);
  const avgPerDay = searchAnalytics.length > 0 ? totalSearches / searchAnalytics.length : 0;
  const bestDay = searchAnalytics.reduce<{ day: string; searches: number }>(
    (best, d) => (d.searches > best.searches ? d : best),
    { day: "—", searches: 0 },
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Search Performance</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Search volume over the last 7 days</p>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={searchAnalytics.length === 0}
        emptyMessage="No search activity yet."
        className="min-h-[200px] p-6"
      >
      <CardContent className="pt-4">
        <div className="mb-4 flex flex-wrap gap-2">
          <div className="rounded-lg border border-border bg-surface-2/60 px-3 py-2">
            <p className="text-xs text-muted-foreground">Avg. searches / day</p>
            <p className="text-sm font-semibold tabular-nums">{avgPerDay.toFixed(1)}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/60 px-3 py-2">
            <p className="text-xs text-muted-foreground">Best day</p>
            <p className="text-sm font-semibold tabular-nums">
              {bestDay.day} &middot; {bestDay.searches}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/60 px-3 py-2">
            <p className="text-xs text-muted-foreground">Total this week</p>
            <p className="text-sm font-semibold tabular-nums">{totalSearches}</p>
          </div>
        </div>
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={searchAnalytics} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
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
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--color-surface-2)" }} />
              <Bar dataKey="searches" name="Searches" fill="var(--color-primary)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
      </AsyncContent>
    </Card>
  );
}
