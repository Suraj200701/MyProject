"use client";

import * as React from "react";
import type { Table } from "@tanstack/react-table";
import { toast } from "sonner";
import {
  Bookmark,
  ChevronDown,
  Columns3,
  Download,
  Loader2,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import type { Lead } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { OPTIONAL_COLUMN_LABELS } from "@/components/leads/columns";
import { errorMessage } from "@/lib/api/client";
import { exportsApi } from "@/lib/api/endpoints";
import {
  useCountryAnalytics,
  useDeleteLeads,
  useImportLeadsCsv,
  useTopIndustries,
} from "@/lib/api/queries";

/**
 * Saved views, expressed as real filter presets.
 *
 * These used to be four labels that fired a toast and changed nothing. Each now
 * maps to filters `GET /leads` actually supports, so switching a view re-queries
 * the server. The former "This Week" view is gone: the endpoint has no
 * date-range parameter, so it could only ever have been decorative.
 */
export interface SavedView {
  label: string;
  filters: { status?: string; minScore?: number };
}

export const SAVED_VIEWS: SavedView[] = [
  { label: "All Leads", filters: {} },
  { label: "High Value", filters: { minScore: 80 } },
  { label: "Untouched", filters: { status: "new" } },
];

export function LeadsToolbar({
  table,
  search,
  onSearchChange,
  industryFilter,
  onIndustryFilterChange,
  statusFilter,
  onStatusFilterChange,
  countryFilter,
  onCountryFilterChange,
  activeView,
  onViewChange,
  selectedIds,
  onClearSelection,
}: {
  table: Table<Lead>;
  search: string;
  onSearchChange: (value: string) => void;
  industryFilter: string;
  onIndustryFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  countryFilter: string;
  onCountryFilterChange: (value: string) => void;
  activeView: string;
  onViewChange: (view: SavedView) => void;
  selectedIds: string[];
  onClearSelection: () => void;
}) {
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [exporting, setExporting] = React.useState(false);

  /**
   * Filter options come from the analytics endpoints, which aggregate across the
   * whole lead table. Deriving them from the rows on screen — as the previous
   * version did from the full fixture — would mean the dropdowns only offered
   * values from the current page.
   */
  const { data: industriesData } = useTopIndustries();
  const { data: countriesData } = useCountryAnalytics();
  const industries = React.useMemo(
    () => (industriesData ?? []).map((i) => i.name).filter(Boolean).sort(),
    [industriesData],
  );
  const countries = React.useMemo(
    () => (countriesData ?? []).map((c) => c.country).filter(Boolean).sort(),
    [countriesData],
  );

  const deleteLeads = useDeleteLeads();
  const importCsv = useImportLeadsCsv();
  const selectedCount = selectedIds.length;

  async function handleBulkExport() {
    setExporting(true);
    try {
      // A real export of exactly the selected rows, via the Export Center's
      // scope="selected" mode, downloaded with a signed token.
      const created = await exportsApi.create({
        resource: "leads",
        format: "csv",
        scope: "selected",
        lead_ids: selectedIds,
      });
      if (created.status !== "ready") {
        toast.success("Export queued — track it in the Export Center.");
        return;
      }
      const url = await exportsApi.downloadUrl(created.id);
      window.location.href = url;
      toast.success(`Exported ${created.row_count} lead${created.row_count === 1 ? "" : "s"}.`);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setExporting(false);
    }
  }

  function handleBulkDelete() {
    deleteLeads.mutate(selectedIds, {
      onSuccess: () => {
        toast.success(`Deleted ${selectedCount} lead${selectedCount === 1 ? "" : "s"}.`);
        onClearSelection();
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  }

  function handleImportFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Reset immediately so picking the same file twice still fires a change.
    event.target.value = "";
    if (!file) return;

    importCsv.mutate(file, {
      onSuccess: (result) => {
        const parts = [`Imported ${result.imported} lead${result.imported === 1 ? "" : "s"}`];
        if (result.duplicates_skipped > 0) parts.push(`${result.duplicates_skipped} duplicate(s) skipped`);
        if (result.invalid_rows > 0) parts.push(`${result.invalid_rows} row(s) had issues`);
        toast.success(parts.join(" · "), {
          description: result.errors.length
            ? `First issue: line ${result.errors[0].line} — ${result.errors[0].message}`
            : undefined,
        });
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  }

  return (
    <div className="flex flex-col gap-3 mb-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by company name..."
            className="pl-8"
          />
        </div>

        <Select value={industryFilter} onValueChange={onIndustryFilterChange}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Industry" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All industries</SelectItem>
            {industries.map((industry) => (
              <SelectItem key={industry} value={industry}>
                {industry}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={onStatusFilterChange}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="new">New</SelectItem>
            <SelectItem value="contacted">Contacted</SelectItem>
            <SelectItem value="qualified">Qualified</SelectItem>
            <SelectItem value="converted">Converted</SelectItem>
            <SelectItem value="lost">Lost</SelectItem>
          </SelectContent>
        </Select>

        <Select value={countryFilter} onValueChange={onCountryFilterChange}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Country" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All countries</SelectItem>
            {countries.map((country) => (
              <SelectItem key={country} value={country}>
                {country}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              <Bookmark className="size-3.5" />
              {activeView}
              <ChevronDown className="size-3.5 opacity-60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuLabel>Saved views</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {SAVED_VIEWS.map((view) => (
              <DropdownMenuItem key={view.label} onSelect={() => onViewChange(view)}>
                {view.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              <Columns3 className="size-3.5" />
              Columns
              <ChevronDown className="size-3.5 opacity-60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Toggle columns</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {table
              .getAllLeafColumns()
              .filter((column) => column.getCanHide())
              .map((column) => (
                <DropdownMenuCheckboxItem
                  key={column.id}
                  checked={column.getIsVisible()}
                  onCheckedChange={(value) => column.toggleVisibility(!!value)}
                  onSelect={(e) => e.preventDefault()}
                >
                  {OPTIONAL_COLUMN_LABELS[column.id] ?? column.id}
                </DropdownMenuCheckboxItem>
              ))}
          </DropdownMenuContent>
        </DropdownMenu>

        {/* This button used to be labelled "Add Leads" and toasted "New view
            created" — the wrong action, and a fake one. It now performs a real
            CSV import via POST /leads/import, which the backend supported but
            nothing in the UI reached. Rows are deduplicated and scored
            server-side. */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={handleImportFile}
        />
        <Button
          variant="secondary"
          size="sm"
          className="ml-auto"
          disabled={importCsv.isPending}
          onClick={() => fileInputRef.current?.click()}
        >
          {importCsv.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Upload className="size-3.5" />
          )}
          {importCsv.isPending ? "Importing..." : "Import CSV"}
        </Button>
      </div>

      {selectedCount > 0 && (
        <div className="flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 animate-fade-in">
          <span className="text-xs font-medium text-foreground">
            {selectedCount} lead{selectedCount === 1 ? "" : "s"} selected
          </span>
          <div className="ml-auto flex items-center gap-2">
            {/* The bulk "Tag" button was removed: there is no bulk-tag endpoint
                and no UI to ask which tag to apply, so it could only ever have
                shown a toast. Tags remain editable per lead on the profile. */}
            <Button variant="secondary" size="sm" disabled={exporting} onClick={handleBulkExport}>
              {exporting ? <Loader2 className="size-3.5 animate-spin" /> : <Download className="size-3.5" />}
              Export
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={deleteLeads.isPending}
              onClick={handleBulkDelete}
            >
              {deleteLeads.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Trash2 className="size-3.5" />
              )}
              Delete
            </Button>
            <Button variant="ghost" size="icon" className="size-8" onClick={onClearSelection}>
              <X className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
