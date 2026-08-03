"use client";

import { formatDistanceToNow } from "date-fns";
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AsyncContent } from "@/components/shared/async-content";
import { useImportHistory } from "@/lib/api/queries";
import type { ImportStatus, LeadImportOut } from "@/lib/api/types";

const STATUS: Record<
  ImportStatus,
  { label: string; variant: "success" | "warning" | "danger" | "outline"; Icon: typeof CheckCircle2 }
> = {
  completed: { label: "Completed", variant: "success", Icon: CheckCircle2 },
  completed_empty: { label: "Nothing new", variant: "warning", Icon: AlertTriangle },
  failed: { label: "Failed", variant: "danger", Icon: XCircle },
  processing: { label: "Processing", variant: "outline", Icon: Loader2 },
};

/** Human label for a run: the search it came from, else the filename. */
function describe(entry: LeadImportOut): string {
  if (entry.keyword) {
    return entry.location ? `${entry.keyword} in ${entry.location}` : entry.keyword;
  }
  return entry.file_name ?? "CSV import";
}

export function ImportHistory() {
  const { data, isPending, isError, error } = useImportHistory({ page_size: 10 });
  const items = data?.items ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Import history</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          Every run, including failures. Counts are recorded at import time, so they
          stay accurate after leads are edited.
        </p>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={items.length === 0}
        emptyMessage="No imports yet."
        className="min-h-[120px] p-5"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="px-5 py-2 font-medium">Search / file</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 text-right font-medium">Imported</th>
                <th className="px-3 py-2 text-right font-medium">Dupes</th>
                <th className="px-3 py-2 text-right font-medium">Invalid</th>
                <th className="px-5 py-2 text-right font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {items.map((entry) => {
                const status = STATUS[entry.status];
                return (
                  <tr key={entry.id} className="border-b border-border/50 last:border-0">
                    <td className="max-w-[240px] truncate px-5 py-2.5">
                      <span className="font-medium">{describe(entry)}</span>
                      {entry.source === "google_maps_extractor" ? (
                        <span className="ml-1.5 text-[11px] text-muted-foreground">· Maps</span>
                      ) : null}
                      {entry.error_message ? (
                        <p className="truncate text-[11px] text-danger">{entry.error_message}</p>
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge variant={status.variant} className="gap-1">
                        <status.Icon
                          className={`size-3 ${entry.status === "processing" ? "animate-spin" : ""}`}
                        />
                        {status.label}
                      </Badge>
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{entry.imported}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-muted-foreground">
                      {entry.duplicates_skipped}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-muted-foreground">
                      {entry.invalid_rows}
                    </td>
                    <td className="px-5 py-2.5 text-right text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </AsyncContent>
    </Card>
  );
}
