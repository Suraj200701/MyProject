"use client";

import { useQueryClient } from "@tanstack/react-query";

import { PageHeader } from "@/components/shared/page-header";
import { ExportWizard } from "@/components/export/export-wizard";
import { DownloadCenter } from "@/components/export/download-center";
import { ExportAnalyticsChart } from "@/components/export/export-analytics-chart";
import { queryKeys } from "@/lib/api/queries";

export default function ExportPage() {
  const queryClient = useQueryClient();

  return (
    <div>
      <PageHeader
        title="Export Center"
        description="Export your leads to CSV, Excel, PDF, or JSON — with a full history of past exports."
        actions={
          <ExportWizard
            // The wizard's mutation already invalidates the exports queries, so
            // the Download Center refreshes itself. This extra nudge covers the
            // case where the wizard is closed before its mutation settles.
            onComplete={() => queryClient.invalidateQueries({ queryKey: queryKeys.exports })}
          />
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {/* Fetches its own page of history from GET /exports. */}
          <DownloadCenter />
        </div>
        <ExportAnalyticsChart />
      </div>
    </div>
  );
}
