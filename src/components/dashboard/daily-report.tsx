import { ArrowUpRight, FileBarChart } from "lucide-react";
import Link from "next/link";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { dashboardStats } from "@/lib/mock-data";

const metrics = [
  { label: "New leads today", value: dashboardStats.todayLeads.toLocaleString() },
  { label: "Searches run", value: "18" },
  { label: "Conversion rate", value: `${dashboardStats.conversionRate}%` },
  { label: "Credits used", value: `${dashboardStats.creditsTotal - dashboardStats.creditsRemaining}` },
];

export function DailyReport() {
  return (
    <Card className="glass-strong glow-ring relative overflow-hidden">
      <div className="pointer-events-none absolute -right-10 -top-10 size-40 rounded-full bg-primary/20 blur-3xl" />
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <div className="flex size-7 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <FileBarChart className="size-3.5" />
        </div>
        <CardTitle>Today at a Glance</CardTitle>
      </CardHeader>
      <div className="grid grid-cols-2 gap-4 p-5 pt-3">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <p className="text-lg font-semibold tracking-tight">{metric.value}</p>
            <p className="text-xs text-muted-foreground">{metric.label}</p>
          </div>
        ))}
      </div>
      <div className="border-t border-border px-5 py-3">
        <Link
          href="/dashboard/intelligence"
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          View full report
          <ArrowUpRight className="size-3" />
        </Link>
      </div>
    </Card>
  );
}
