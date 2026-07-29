"use client";

import { formatDistanceToNowStrict } from "date-fns";
import { Braces, Download, FileSpreadsheet, FileText, Sheet } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import type { ExportFormat, ExportRecord } from "@/components/export/types";

const FORMAT_ICON: Record<ExportFormat, typeof FileText> = {
  CSV: Sheet,
  Excel: FileSpreadsheet,
  PDF: FileText,
  JSON: Braces,
};

export function DownloadCenter({ exports }: { exports: ExportRecord[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Download Center</CardTitle>
      </CardHeader>
      <CardContent>
        {exports.length === 0 ? (
          <EmptyState icon={Download} title="No exports yet" description="Start a new export to see it appear here." />
        ) : (
          <div className="divide-y divide-border/60">
            {exports.map((exp) => {
              const Icon = FORMAT_ICON[exp.format];
              return (
                <div key={exp.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
                    <Icon className="size-4 text-muted-foreground" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{exp.fileName}</p>
                    <p className="text-xs text-muted-foreground">
                      {exp.rowCount.toLocaleString()} rows · {exp.sizeLabel} ·{" "}
                      {formatDistanceToNowStrict(new Date(exp.createdAt), { addSuffix: true })}
                    </p>
                  </div>
                  <Badge variant={exp.status === "ready" ? "success" : "outline"}>
                    {exp.status === "ready" ? "Ready" : "Expired"}
                  </Badge>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={exp.status === "expired"}
                    onClick={() => toast.success(`Downloading ${exp.fileName}`)}
                  >
                    <Download className="size-4" />
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
