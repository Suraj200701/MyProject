export type ExportFormat = "CSV" | "Excel" | "PDF" | "JSON";
export type ExportSource = "all" | "filtered" | "selected";
export type ExportStatus = "ready" | "expired";

export interface ExportRecord {
  id: string;
  fileName: string;
  format: ExportFormat;
  rowCount: number;
  sizeLabel: string;
  createdAt: string;
  status: ExportStatus;
}

export const EXPORT_FIELDS = [
  "Company",
  "Industry",
  "City",
  "Contact",
  "Email",
  "Phone",
  "Lead Score",
  "Status",
] as const;
