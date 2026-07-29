"use client";

import { formatDistanceToNow } from "date-fns";
import { History, Search, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { SearchHistoryItem } from "@/lib/types";

export interface LiveSearchEntry {
  query: string;
  location: string;
  status: "running" | "completed";
  results: number;
}

function statusBadge(status: SearchHistoryItem["status"] | "running") {
  switch (status) {
    case "completed":
      return (
        <Badge variant="success">
          <CheckCircle2 className="size-3" />
          Completed
        </Badge>
      );
    case "running":
      return (
        <Badge variant="primary">
          <Loader2 className="size-3 animate-spin" />
          Running
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="danger">
          <XCircle className="size-3" />
          Failed
        </Badge>
      );
  }
}

export function SearchTimeline({
  history,
  live,
}: {
  history: SearchHistoryItem[];
  live?: LiveSearchEntry | null;
}) {
  return (
    <Card className="glass">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-[13px] uppercase tracking-wide text-muted-foreground">
          <History className="size-3.5" />
          Search timeline
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4">
        <ul className="space-y-3">
          {live && (
            <li className="flex items-start gap-3">
              <div className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary/10">
                <Search className="size-3.5 text-primary" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium truncate">{live.query || "New search"}</p>
                  {statusBadge(live.status)}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {live.location || "All locations"} · {live.results} results · just now
                </p>
              </div>
            </li>
          )}
          {history.map((item) => (
            <li key={item.id} className="flex items-start gap-3">
              <div className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
                <Search className="size-3.5 text-muted-foreground" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium truncate">{item.query}</p>
                  {statusBadge(item.status)}
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {item.location} · {item.results} results ·{" "}
                  {formatDistanceToNow(new Date(item.createdAt), { addSuffix: true })}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
