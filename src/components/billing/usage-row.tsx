"use client";

import { Database, Download, Search, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsage } from "@/lib/api/queries";

export function UsageRow() {
  const { data, isPending } = useUsage();

  // `UsageOut` reports credits *used* against the plan limit, which is exactly
  // what these tiles show — no inversion needed here.
  const tiles = [
    { icon: Database, label: "API Credits", used: data?.credits_used, limit: data?.credits_limit },
    { icon: Users, label: "Team Seats", used: data?.seats_used, limit: data?.seats_limit },
    { icon: Search, label: "Searches", used: data?.searches_this_month, limit: null },
    { icon: Download, label: "Exports", used: data?.exports_this_month, limit: null },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {tiles.map((tile) => {
        // An unlimited (or unreported) allowance has no meaningful percentage,
        // and a zero limit would render NaN%.
        const pct =
          tile.limit && tile.limit > 0 && tile.used != null
            ? Math.min(100, Math.round((tile.used / tile.limit) * 100))
            : null;

        return (
          <Card key={tile.label} className="p-4">
            <CardContent className="p-0">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <tile.icon className="size-4" />
                {tile.label}
              </div>
              {isPending || tile.used == null ? (
                <Skeleton className="mt-2 h-7 w-24" />
              ) : (
                <p className="mt-2 text-lg font-semibold tabular-nums">
                  {tile.used.toLocaleString()}
                  {tile.limit ? (
                    <span className="text-sm font-normal text-muted-foreground">
                      {" "}
                      / {tile.limit.toLocaleString()}
                    </span>
                  ) : (
                    <span className="text-sm font-normal text-muted-foreground"> this month</span>
                  )}
                </p>
              )}
              {/* The bar only appears where there is a real ceiling to fill. */}
              {pct !== null ? <Progress value={pct} className="mt-2" /> : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
