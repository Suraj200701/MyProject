"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { mockLeads } from "@/lib/mock-data";

const BANDS = [
  { id: "excellent", label: "Excellent (85+)", min: 85, max: 101, color: "bg-success" },
  { id: "good", label: "Good (70-84)", min: 70, max: 85, color: "bg-primary" },
  { id: "fair", label: "Fair (50-69)", min: 50, max: 70, color: "bg-warning" },
  { id: "weak", label: "Weak (<50)", min: 0, max: 50, color: "bg-danger" },
] as const;

export function LeadQualityCard() {
  const counts = BANDS.map((band) => ({
    ...band,
    count: mockLeads.filter((l) => l.leadScore >= band.min && l.leadScore < band.max).length,
  }));
  const total = mockLeads.length;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Lead Quality</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">Distribution of leads by score band</p>
      </CardHeader>
      <CardContent>
        <div className="flex h-3 w-full overflow-hidden rounded-full">
          {counts.map((b) => (
            <div
              key={b.id}
              className={b.color}
              style={{ width: `${total > 0 ? (b.count / total) * 100 : 0}%` }}
              title={`${b.label}: ${b.count}`}
            />
          ))}
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3">
          {counts.map((b) => (
            <div key={b.id} className="flex items-center gap-2">
              <span className={`size-2.5 shrink-0 rounded-full ${b.color}`} />
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-foreground">{b.label}</p>
                <p className="text-xs text-muted-foreground">
                  {b.count.toLocaleString()} · {total > 0 ? ((b.count / total) * 100).toFixed(0) : 0}%
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
