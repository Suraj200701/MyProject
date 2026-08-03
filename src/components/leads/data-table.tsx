"use client";

import * as React from "react";
import {
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { AlertCircle, ChevronLeft, ChevronRight, Search as SearchIcon } from "lucide-react";

import { leadColumns } from "@/components/leads/columns";
import { LeadsToolbar, type SavedView } from "@/components/leads/leads-toolbar";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useLeads } from "@/lib/api/queries";
import type { LeadsQuery } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;

/** Debounce the search box so typing doesn't fire a request per keystroke. */
function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * The lead table, now backed by `GET /leads`.
 *
 * Pagination, sorting and filtering all run **server-side** (`manualPagination`,
 * `manualSorting`, `manualFiltering`). That is the substantive change: the
 * previous version loaded every lead into the browser and filtered in memory,
 * which stops working the moment an organization has more leads than fit in a
 * response. The markup, columns, toolbar and empty state are unchanged.
 */
export function LeadsDataTable() {
  const router = useRouter();

  const [search, setSearch] = React.useState("");
  const debouncedSearch = useDebounced(search, 300);
  const [industryFilter, setIndustryFilter] = React.useState("all");
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [countryFilter, setCountryFilter] = React.useState("all");
  const [minScore, setMinScore] = React.useState<number | undefined>(undefined);
  const [activeView, setActiveView] = React.useState("All Leads");

  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({});
  const [rowSelection, setRowSelection] = React.useState<RowSelectionState>({});
  const [pageIndex, setPageIndex] = React.useState(0);

  // Any filter change invalidates the current page number.
  React.useEffect(() => {
    setPageIndex(0);
  }, [debouncedSearch, industryFilter, statusFilter, countryFilter, minScore, sorting]);

  /** Maps the table's sort state onto the columns the API can sort by. */
  const sortParams = React.useMemo((): Pick<LeadsQuery, "sort_by" | "sort_order"> => {
    const active = sorting[0];
    if (!active) return {};
    const sortable: Record<string, LeadsQuery["sort_by"]> = {
      company: "company",
      leadScore: "lead_score",
      createdAt: "created_at",
    };
    const sort_by = sortable[active.id];
    // Columns the API can't sort on (city, provider, …) are left unsorted rather
    // than silently sorted by something else.
    if (!sort_by) return {};
    return { sort_by, sort_order: active.desc ? "desc" : "asc" };
  }, [sorting]);

  const query: LeadsQuery = {
    page: pageIndex + 1,
    page_size: PAGE_SIZE,
    search: debouncedSearch || undefined,
    industry: industryFilter !== "all" ? industryFilter : undefined,
    status: statusFilter !== "all" ? statusFilter : undefined,
    country: countryFilter !== "all" ? countryFilter : undefined,
    min_score: minScore,
    ...sortParams,
  };

  const { data, isPending, isError, error, isPlaceholderData } = useLeads(query);
  const rowsData = React.useMemo(() => data?.items ?? [], [data]);
  const meta = data?.meta;

  // React Compiler cannot memoize a component that calls `useReactTable`: the
  // instance it returns carries functions whose identity is meaningful, and
  // memoizing them would serve stale rows. The compiler's own remedy is to skip
  // optimizing this component, which is correct and costs nothing here — the
  // table renders one page at a time. Silencing the advisory keeps `npm run
  // lint` clean so a real warning is not lost in the noise.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: rowsData,
    columns: leadColumns,
    state: { sorting, columnVisibility, rowSelection },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    // The server owns paging/sorting/filtering; the table just renders the page.
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
    pageCount: meta?.total_pages ?? 0,
    getRowId: (row) => row.id,
    getCoreRowModel: getCoreRowModel(),
  });

  const rows = table.getRowModel().rows;
  const selectedIds = React.useMemo(() => Object.keys(rowSelection), [rowSelection]);

  function applyView(view: SavedView) {
    setActiveView(view.label);
    setStatusFilter(view.filters.status ?? "all");
    setMinScore(view.filters.minScore);
  }

  function clearFilters() {
    setSearch("");
    setIndustryFilter("all");
    setStatusFilter("all");
    setCountryFilter("all");
    setMinScore(undefined);
    setActiveView("All Leads");
  }

  const hasFilters =
    !!debouncedSearch ||
    industryFilter !== "all" ||
    statusFilter !== "all" ||
    countryFilter !== "all" ||
    minScore !== undefined;

  return (
    <div>
      <LeadsToolbar
        table={table}
        search={search}
        onSearchChange={setSearch}
        industryFilter={industryFilter}
        onIndustryFilterChange={setIndustryFilter}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        countryFilter={countryFilter}
        onCountryFilterChange={setCountryFilter}
        activeView={activeView}
        onViewChange={applyView}
        selectedIds={selectedIds}
        onClearSelection={() => setRowSelection({})}
      />

      {isPending ? (
        <div className="overflow-hidden rounded-xl border border-border p-4">
          <div className="flex flex-col gap-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-11 rounded-lg" />
            ))}
          </div>
        </div>
      ) : isError ? (
        <EmptyState
          icon={AlertCircle}
          title="Couldn't load your leads"
          description={error instanceof Error ? error.message : "Something went wrong."}
        />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={SearchIcon}
          title={hasFilters ? "No leads match your filters" : "No leads yet"}
          description={
            hasFilters
              ? "Try adjusting your search or clearing filters to see more results."
              : "Run a search or import a CSV to start building your lead database."
          }
          actionLabel={hasFilters ? "Clear filters" : undefined}
          onAction={hasFilters ? clearFilters : undefined}
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <div className={cn("overflow-x-auto", isPlaceholderData && "opacity-60 transition-opacity")}>
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-surface-2/80 backdrop-blur">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id} className="border-b border-border">
                    {headerGroup.headers.map((header) => (
                      <th
                        key={header.id}
                        className="px-4 py-3 text-left font-medium"
                        style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => router.push(`/dashboard/leads/${row.original.id}`)}
                    className={cn(
                      "cursor-pointer border-b border-border/60 last:border-0 transition-colors hover:bg-surface-2/50",
                      row.getIsSelected() && "bg-primary/[0.04]",
                    )}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-3 align-middle">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between border-t border-border px-4 py-3">
            <p className="text-xs text-muted-foreground">
              Showing {rows.length} of {(meta?.total_items ?? 0).toLocaleString()} leads
            </p>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                Page {(meta?.page ?? 1).toLocaleString()} of{" "}
                {Math.max(1, meta?.total_pages ?? 1).toLocaleString()}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="icon"
                  className="size-8"
                  disabled={!meta?.has_previous}
                  onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="size-8"
                  disabled={!meta?.has_next}
                  onClick={() => setPageIndex((p) => p + 1)}
                >
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
