"use client";

import * as React from "react";
import type { Table } from "@tanstack/react-table";
import { toast } from "sonner";
import {
  Bookmark,
  ChevronDown,
  Columns3,
  Download,
  Plus,
  Search,
  Tags,
  Trash2,
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

const SAVED_VIEWS = ["All Leads", "High Value", "This Week", "Untouched"];

export function LeadsToolbar({
  table,
  data,
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
}: {
  table: Table<Lead>;
  data: Lead[];
  search: string;
  onSearchChange: (value: string) => void;
  industryFilter: string;
  onIndustryFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  countryFilter: string;
  onCountryFilterChange: (value: string) => void;
  activeView: string;
  onViewChange: (value: string) => void;
}) {
  const industries = React.useMemo(
    () => Array.from(new Set(data.map((lead) => lead.industry))).sort(),
    [data],
  );
  const countries = React.useMemo(
    () => Array.from(new Set(data.map((lead) => lead.country))).sort(),
    [data],
  );

  const selectedCount = table.getFilteredSelectedRowModel().rows.length;

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
              <DropdownMenuItem
                key={view}
                onSelect={() => {
                  onViewChange(view);
                  toast.success(`Switched to "${view}" view`);
                }}
              >
                {view}
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

        <Button variant="secondary" size="sm" className="ml-auto" onClick={() => toast.success("New view created")}>
          <Plus className="size-3.5" />
          Add Leads
        </Button>
      </div>

      {selectedCount > 0 && (
        <div className="flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 animate-fade-in">
          <span className="text-xs font-medium text-foreground">
            {selectedCount} lead{selectedCount === 1 ? "" : "s"} selected
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => toast.success(`Exporting ${selectedCount} lead${selectedCount === 1 ? "" : "s"}`)}
            >
              <Download className="size-3.5" />
              Export
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => toast.success(`Tagged ${selectedCount} lead${selectedCount === 1 ? "" : "s"}`)}
            >
              <Tags className="size-3.5" />
              Tag
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                toast.error(`Deleted ${selectedCount} lead${selectedCount === 1 ? "" : "s"}`);
                table.resetRowSelection();
              }}
            >
              <Trash2 className="size-3.5" />
              Delete
            </Button>
            <Button variant="ghost" size="icon" className="size-8" onClick={() => table.resetRowSelection()}>
              <X className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
