export type ExportFormat = "CSV" | "Excel" | "PDF" | "JSON";
export type ExportSource = "all" | "filtered" | "selected";

/**
 * Export lifecycle states.
 *
 * Extended beyond the original `"ready" | "expired"` because the backend has two
 * more real states: `processing` (a large export queued to a worker) and `failed`
 * (with a reason). Omitting them would mean rendering a queued export as though
 * its file were already downloadable.
 */
export type ExportStatus = "ready" | "expired" | "processing" | "failed";

export interface ExportRecord {
  id: string;
  fileName: string;
  format: ExportFormat;
  rowCount: number;
  sizeLabel: string;
  createdAt: string;
  status: ExportStatus;
  /** Populated only when `status` is "failed". */
  errorMessage?: string;
  /** What the export contains, from the backend's `resource` field. */
  resource?: string;
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
