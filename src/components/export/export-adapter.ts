import type { ExportFormatApi, ExportOut, ExportScopeApi } from "@/lib/api/types";
import type { ExportFormat, ExportRecord, ExportSource } from "@/components/export/types";

/**
 * Translation between the wizard's labels and the export API.
 *
 * The wizard was built with title-case format labels ("Excel") while the API uses
 * lowercase enum values ("excel"), and the file extension for Excel is `.xlsx`
 * rather than `.excel`. Keeping that mapping in one place stops the three
 * spellings drifting apart.
 *
 * `ExportSource` already matches the API's `scope` union exactly, so it passes
 * through unchanged.
 */

const FORMAT_TO_API: Record<ExportFormat, ExportFormatApi> = {
  CSV: "csv",
  Excel: "excel",
  PDF: "pdf",
  JSON: "json",
};

const API_TO_FORMAT: Record<ExportFormatApi, ExportFormat> = {
  csv: "CSV",
  excel: "Excel",
  pdf: "PDF",
  json: "JSON",
};

export const toApiFormat = (format: ExportFormat): ExportFormatApi => FORMAT_TO_API[format];

export const toApiScope = (source: ExportSource): ExportScopeApi => source;

/** `ExportOut` -> the `ExportRecord` the Download Center renders. */
export function toExportRecord(dto: ExportOut): ExportRecord {
  return {
    id: dto.id,
    fileName: dto.file_name,
    format: API_TO_FORMAT[dto.format] ?? "CSV",
    rowCount: dto.row_count,
    // Pre-formatted server-side, so the size shown always matches the size
    // recorded — no duplicated rounding rules in the client.
    sizeLabel: dto.size_label,
    createdAt: dto.created_at,
    status: dto.status,
    errorMessage: dto.error_message ?? undefined,
    resource: dto.resource,
  };
}

/** Human label for the `resource` field, for the history rows. */
export function resourceLabel(resource: string | undefined): string {
  switch (resource) {
    case "leads":
      return "Leads";
    case "search_results":
      return "Search results";
    case "dashboard_report":
      return "Dashboard report";
    case "analytics_report":
      return "Analytics report";
    default:
      return "Export";
  }
}
