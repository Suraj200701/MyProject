import { Database, Download, Search, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { dashboardStats } from "@/lib/mock-data";

const USAGE = [
  {
    icon: Database,
    label: "API Credits",
    used: dashboardStats.creditsTotal - dashboardStats.creditsRemaining,
    limit: dashboardStats.creditsTotal,
  },
  { icon: Users, label: "Team Seats", used: 6, limit: 20 },
  { icon: Search, label: "Searches", used: 341, limit: 500 },
  { icon: Download, label: "Exports", used: 34, limit: 100 },
];

export function UsageRow() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {USAGE.map((u) => {
        const pct = Math.round((u.used / u.limit) * 100);
        return (
          <Card key={u.label} className="p-4">
            <CardContent className="p-0">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <u.icon className="size-4" />
                {u.label}
              </div>
              <p className="mt-2 text-lg font-semibold tabular-nums">
                {u.used.toLocaleString()} <span className="text-sm font-normal text-muted-foreground">/ {u.limit.toLocaleString()}</span>
              </p>
              <Progress value={pct} className="mt-2" />
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
