import { type LucideIcon, TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  change,
  icon: Icon,
  accent = "primary",
}: {
  label: string;
  value: string;
  change?: { value: string; positive: boolean };
  icon: LucideIcon;
  accent?: "primary" | "accent" | "success" | "warning";
}) {
  return (
    <Card className="relative overflow-hidden p-5 hover:border-border-strong transition-colors group">
      <div
        className={cn(
          "absolute -right-6 -top-6 size-24 rounded-full blur-2xl opacity-20 transition-opacity group-hover:opacity-30",
          accent === "primary" && "bg-primary",
          accent === "accent" && "bg-accent",
          accent === "success" && "bg-success",
          accent === "warning" && "bg-warning",
        )}
      />
      <div className="flex items-start justify-between">
        <p className="text-sm text-muted-foreground">{label}</p>
        <div
          className={cn(
            "flex size-8 items-center justify-center rounded-lg border border-border bg-surface-2",
          )}
        >
          <Icon className="size-4 text-foreground/80" />
        </div>
      </div>
      <p className="mt-3 text-2xl font-semibold tracking-tight">{value}</p>
      {change && (
        <div
          className={cn(
            "mt-2 inline-flex items-center gap-1 text-xs font-medium",
            change.positive ? "text-success" : "text-danger",
          )}
        >
          {change.positive ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
          {change.value}
        </div>
      )}
    </Card>
  );
}
