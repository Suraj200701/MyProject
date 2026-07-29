import type { ExportRecord } from "@/components/export/types";

export const INITIAL_EXPORTS: ExportRecord[] = [
  { id: "exp-1", fileName: "leads_july_panel_builders.xlsx", format: "Excel", rowCount: 214, sizeLabel: "1.2 MB", createdAt: "2026-07-28T09:12:00Z", status: "ready" },
  { id: "exp-2", fileName: "electrical_dealers_mumbai.csv", format: "CSV", rowCount: 178, sizeLabel: "410 KB", createdAt: "2026-07-27T14:30:00Z", status: "ready" },
  { id: "exp-3", fileName: "high_value_leads_q3.json", format: "JSON", rowCount: 92, sizeLabel: "260 KB", createdAt: "2026-07-25T11:00:00Z", status: "ready" },
  { id: "exp-4", fileName: "epc_companies_uae.pdf", format: "PDF", rowCount: 61, sizeLabel: "890 KB", createdAt: "2026-07-18T08:45:00Z", status: "expired" },
  { id: "exp-5", fileName: "system_integrators_singapore.xlsx", format: "Excel", rowCount: 47, sizeLabel: "310 KB", createdAt: "2026-07-10T16:20:00Z", status: "expired" },
];

export const FORMAT_META: Record<string, { description: string; sizeHint: string }> = {
  CSV: { description: "Universal, lightweight, opens in any spreadsheet tool", sizeHint: "~200-500 KB" },
  Excel: { description: "Formatted workbook with styled columns", sizeHint: "~0.8-2 MB" },
  PDF: { description: "Print-ready summary report", sizeHint: "~0.5-1.2 MB" },
  JSON: { description: "Structured data for developers & integrations", sizeHint: "~150-400 KB" },
};
