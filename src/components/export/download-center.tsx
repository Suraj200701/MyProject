"use client";

import * as React from "react";
import { formatDistanceToNowStrict } from "date-fns";
import {
  AlertCircle,
  Braces,
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
  Sheet,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { AsyncContent, SkeletonRows } from "@/components/shared/async-content";
import { resourceLabel, toExportRecord } from "@/components/export/export-adapter";
import type { ExportFormat, ExportStatus } from "@/components/export/types";
import { errorMessage } from "@/lib/api/client";
import { exportsApi } from "@/lib/api/endpoints";
import { useDeleteExport, useExports } from "@/lib/api/queries";

const FORMAT_ICON: Record<ExportFormat, typeof FileText> = {
  CSV: Sheet,
  Excel: FileSpreadsheet,
  PDF: FileText,
  JSON: Braces,
};

const STATUS_BADGE: Record<
  ExportStatus,
  { label: string; variant: "success" | "outline" | "primary" | "danger" }
> = {
  ready: { label: "Ready", variant: "success" },
  processing: { label: "Processing", variant: "primary" },
  expired: { label: "Expired", variant: "outline" },
  failed: { label: "Failed", variant: "danger" },
};

/**
 * Export history, from `GET /exports`.
 *
 * Fetches its own data rather than taking an `exports` prop, so the list stays in
 * sync with the server after a wizard run, a delete, or a background export
 * finishing. The previous version held a local array seeded from a fixture and
 * only ever grew it in memory, and its download button fired a toast.
 *
 * Failed and expired rows are shown, matching the backend: an audit trail that
 * hides failures can't answer "where did my export go?".
 */
export function DownloadCenter() {
  const { data, isPending, isError, error } = useExports({ page_size: 20 });
  const deleteExport = useDeleteExport();
  const [downloadingId, setDownloadingId] = React.useState<string | null>(null);

  const records = React.useMemo(() => (data?.items ?? []).map(toExportRecord), [data]);

  async function handleDownload(id: string) {
    setDownloadingId(id);
    try {
      // Signed short-lived token, so the browser can fetch the bytes without an
      // Authorization header. `assign()` rather than setting `location.href`:
      // the React Compiler rejects assigning to that property.
      window.location.assign(await exportsApi.downloadUrl(id));
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDownloadingId(null);
    }
  }

  function handleDelete(id: string, fileName: string) {
    deleteExport.mutate(id, {
      onSuccess: () => toast.success(`Deleted ${fileName}`),
      onError: (err) => toast.error(errorMessage(err)),
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Download Center</CardTitle>
      </CardHeader>
      <CardContent>
        <AsyncContent
          isPending={isPending}
          isError={isError}
          error={error}
          className="min-h-[220px]"
          skeleton={<SkeletonRows rows={4} />}
        >
          {records.length === 0 ? (
            <EmptyState
              icon={Download}
              title="No exports yet"
              description="Start a new export to see it appear here."
            />
          ) : (
            <div className="divide-y divide-border/60">
              {records.map((exp) => {
                const Icon = FORMAT_ICON[exp.format] ?? FileText;
                const badge = STATUS_BADGE[exp.status];
                const busy = downloadingId === exp.id;
                return (
                  <div key={exp.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
                      {exp.status === "processing" ? (
                        <Loader2 className="size-4 animate-spin text-primary" />
                      ) : exp.status === "failed" ? (
                        <AlertCircle className="size-4 text-danger" />
                      ) : (
                        <Icon className="size-4 text-muted-foreground" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{exp.fileName}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {exp.status === "failed" && exp.errorMessage
                          ? exp.errorMessage
                          : `${resourceLabel(exp.resource)} · ${exp.rowCount.toLocaleString()} rows · ${
                              exp.sizeLabel
                            } · ${formatDistanceToNowStrict(new Date(exp.createdAt), {
                              addSuffix: true,
                            })}`}
                      </p>
                    </div>
                    <Badge variant={badge.variant}>{badge.label}</Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Download ${exp.fileName}`}
                      disabled={exp.status !== "ready" || busy}
                      onClick={() => handleDownload(exp.id)}
                    >
                      {busy ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Delete ${exp.fileName}`}
                      disabled={deleteExport.isPending}
                      onClick={() => handleDelete(exp.id, exp.fileName)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </AsyncContent>
      </CardContent>
    </Card>
  );
}
