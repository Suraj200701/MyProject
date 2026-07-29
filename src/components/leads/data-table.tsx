"use client";

import * as React from "react";
import {
  type ColumnFiltersState,
  type SortingState,
  type VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";

import type { Lead } from "@/lib/types";
import { leadColumns } from "@/components/leads/columns";
import { leadMatchesQuery } from "@/components/leads/lead-badges";
import { LeadsToolbar } from "@/components/leads/leads-toolbar";
import { EmptyState } from "@/components/shared/empty-state";
import { Button } from "@/components/ui/button";
import { Search as SearchIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function LeadsDataTable({ data }: { data: Lead[] }) {
  const router = useRouter();

  const [search, setSearch] = React.useState("");
  const [industryFilter, setIndustryFilter] = React.useState("all");
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [countryFilter, setCountryFilter] = React.useState("all");
  const [activeView, setActiveView] = React.useState("All Leads");

  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({});
  const [rowSelection, setRowSelection] = React.useState({});
  const [pageSize] = React.useState(20);

  React.useEffect(() => {
    setColumnFilters((prev) => {
      const next = prev.filter((f) => !["industry", "status", "location"].includes(f.id));
      if (industryFilter !== "all") next.push({ id: "industry", value: industryFilter });
      if (statusFilter !== "all") next.push({ id: "status", value: statusFilter });
      if (countryFilter !== "all") next.push({ id: "location", value: countryFilter });
      return next;
    });
  }, [industryFilter, statusFilter, countryFilter]);

  const table = useReactTable({
    data,
    columns: leadColumns,
    state: { sorting, columnFilters, columnVisibility, rowSelection, globalFilter: search },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onGlobalFilterChange: setSearch,
    globalFilterFn: (row, _columnId, filterValue) => leadMatchesQuery(row.original, filterValue),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  });

  const rows = table.getRowModel().rows;
  const pageCount = table.getPageCount();
  const pageIndex = table.getState().pagination.pageIndex;

  return (
    <div>
      <LeadsToolbar
        table={table}
        data={data}
        search={search}
        onSearchChange={setSearch}
        industryFilter={industryFilter}
        onIndustryFilterChange={setIndustryFilter}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        countryFilter={countryFilter}
        onCountryFilterChange={setCountryFilter}
        activeView={activeView}
        onViewChange={setActiveView}
      />

      {rows.length === 0 ? (
        <EmptyState
          icon={SearchIcon}
          title="No leads match your filters"
          description="Try adjusting your search or clearing filters to see more results."
          actionLabel="Clear filters"
          onAction={() => {
            setSearch("");
            setIndustryFilter("all");
            setStatusFilter("all");
            setCountryFilter("all");
          }}
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead className="sticky top-0 z-10 bg-surface-2/80 backdrop-blur">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id} className="border-b border-border">
                    {headerGroup.headers.map((header) => (
                      <th key={header.id} className="px-4 py-3 text-left font-medium" style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}>
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
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
              Showing {rows.length} of {table.getFilteredRowModel().rows.length} leads
            </p>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                Page {pageIndex + 1} of {Math.max(1, pageCount)}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="icon"
                  className="size-8"
                  disabled={!table.getCanPreviousPage()}
                  onClick={() => table.previousPage()}
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="size-8"
                  disabled={!table.getCanNextPage()}
                  onClick={() => table.nextPage()}
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
