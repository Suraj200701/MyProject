import { Search } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { searchHistory } from "@/lib/mock-data";
import type { SearchHistoryItem } from "@/lib/types";

function relativeTime(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

const statusVariant: Record<SearchHistoryItem["status"], "success" | "warning" | "danger"> = {
  completed: "success",
  running: "warning",
  failed: "danger",
};

export function RecentSearches() {
  return (
    <Card className="glass overflow-hidden">
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <div className="flex size-7 items-center justify-center rounded-lg bg-surface-2 text-foreground/80">
          <Search className="size-3.5" />
        </div>
        <CardTitle>Recent Searches</CardTitle>
      </CardHeader>
      <div className="flex flex-col divide-y divide-border p-5 pt-3">
        {searchHistory.map((item) => (
          <div key={item.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground/90">{item.query}</p>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {item.location} · {item.results.toLocaleString()} results · {relativeTime(item.createdAt)}
              </p>
            </div>
            <Badge variant={statusVariant[item.status]} className="shrink-0 capitalize">
              {item.status}
            </Badge>
          </div>
        ))}
      </div>
      <div className="border-t border-border px-5 py-3">
        <Link href="/dashboard/search" className="text-xs font-medium text-primary hover:underline">
          Run a new search
        </Link>
      </div>
    </Card>
  );
}
