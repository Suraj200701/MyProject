"use client";

import * as React from "react";
import { PageHeader } from "@/components/shared/page-header";
import { ExportWizard } from "@/components/export/export-wizard";
import { DownloadCenter } from "@/components/export/download-center";
import { ExportAnalyticsChart } from "@/components/export/export-analytics-chart";
import { INITIAL_EXPORTS } from "@/components/export/mock-data";
import type { ExportRecord } from "@/components/export/types";

export default function ExportPage() {
  const [exports, setExports] = React.useState<ExportRecord[]>(INITIAL_EXPORTS);

  return (
    <div>
      <PageHeader
        title="Export Center"
        description="Export your leads to CSV, Excel, PDF, or JSON — with a full history of past exports."
        actions={<ExportWizard onComplete={(record) => setExports((prev) => [record, ...prev])} />}
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <DownloadCenter exports={exports} />
        </div>
        <ExportAnalyticsChart />
      </div>
    </div>
  );
}
