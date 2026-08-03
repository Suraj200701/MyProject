"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AsyncContent } from "@/components/shared/async-content";
import { useLeadQuality } from "@/lib/api/queries";

/**
 * Band colours, keyed by the backend's band ids.
 *
 * The bands themselves (ids, labels, thresholds, counts and percentages) come
 * from `GET /analytics/lead-quality`, which computes them in SQL across the
 * whole lead table. This card used to recompute them client-side, which would
 * only ever have described the leads currently in memory. Colour is
 * presentation, so it stays here.
 */
const BAND_COLORS: Record<string, string> = {
  excellent: "bg-success",
  good: "bg-primary",
  fair: "bg-warning",
  weak: "bg-danger",
};

export function LeadQualityCard() {
  const { data, isPending, isError, error } = useLeadQuality();
  const bands = data ?? [];
  const total = bands.reduce((sum, b) => sum + b.count, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Lead Quality</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Distribution of leads by score band</p>
      </CardHeader>
      <CardContent>
        <AsyncContent
          isPending={isPending}
          isError={isError}
          error={error}
          isEmpty={total === 0}
          emptyMessage="No leads to score yet."
          className="min-h-[140px]"
        >
          <div className="flex h-3 w-full overflow-hidden rounded-full">
            {bands.map((b) => (
              <div
                key={b.id}
                className={BAND_COLORS[b.id] ?? "bg-muted"}
                style={{ width: `${total > 0 ? (b.count / total) * 100 : 0}%` }}
                title={`${b.label}: ${b.count}`}
              />
            ))}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            {bands.map((b) => (
              <div key={b.id} className="flex items-center gap-2">
                <span className={`size-2.5 shrink-0 rounded-full ${BAND_COLORS[b.id] ?? "bg-muted"}`} />
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-foreground">{b.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {b.count.toLocaleString()} · {b.percentage}%
                  </p>
                </div>
              </div>
            ))}
          </div>
        </AsyncContent>
      </CardContent>
    </Card>
  );
}
