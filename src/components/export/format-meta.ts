/**
 * Static descriptions of each export format, shown in the wizard's format picker.
 *
 * This is UI copy, not data — it describes what a CSV/Excel/PDF/JSON file is and
 * roughly how large it tends to be. It is kept (rather than deleted with the rest
 * of the export fixtures) because there is nothing on the server to source it
 * from; `GET /exports/formats` returns extensions and media types, not prose.
 */

export const FORMAT_META: Record<string, { description: string; sizeHint: string }> = {
  CSV: { description: "Universal, lightweight, opens in any spreadsheet tool", sizeHint: "~200-500 KB" },
  Excel: { description: "Formatted workbook with styled columns", sizeHint: "~0.8-2 MB" },
  PDF: { description: "Print-ready summary report", sizeHint: "~0.5-1.2 MB" },
  JSON: { description: "Structured data for developers & integrations", sizeHint: "~150-400 KB" },
};
