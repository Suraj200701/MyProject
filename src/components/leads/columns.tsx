"use client";

import * as React from "react";
import type { Column, ColumnDef } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, ExternalLink, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { formatDistanceToNowStrict } from "date-fns";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

import type { Lead } from "@/lib/types";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CompanyAvatar, RatingStars, ScoreBadge, StatusBadge } from "@/components/leads/lead-badges";

function SortableHeader({ column, label }: { column: Column<Lead, unknown>; label: string }) {
  const sorted = column.getIsSorted();
  return (
    <button
      type="button"
      onClick={() => column.toggleSorting(sorted === "asc")}
      className="inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
    >
      {label}
      {sorted === "asc" ? (
        <ArrowUp className="size-3.5" />
      ) : sorted === "desc" ? (
        <ArrowDown className="size-3.5" />
      ) : (
        <ArrowUpDown className="size-3.5 opacity-40" />
      )}
    </button>
  );
}

function RowActions({ lead }: { lead: Lead }) {
  const router = useRouter();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="size-8" onClick={(e) => e.stopPropagation()}>
          <MoreHorizontal className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
        <DropdownMenuItem onSelect={() => router.push(`/dashboard/leads/${lead.id}`)}>
          <ExternalLink />
          View
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => toast.success(`Editing ${lead.company}`)}>
          <Pencil />
          Edit
        </DropdownMenuItem>
        <DropdownMenuItem variant="destructive" onSelect={() => toast.error(`${lead.company} removed`)}>
          <Trash2 />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export const leadColumns: ColumnDef<Lead>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && "indeterminate")}
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
        onClick={(e) => e.stopPropagation()}
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
        onClick={(e) => e.stopPropagation()}
      />
    ),
    enableSorting: false,
    enableHiding: false,
    size: 40,
  },
  {
    id: "company",
    accessorKey: "company",
    header: ({ column }) => <SortableHeader column={column} label="Company" />,
    cell: ({ row }) => (
      <div className="flex items-center gap-3 min-w-[200px]">
        <CompanyAvatar company={row.original.company} />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground">{row.original.company}</p>
          <p className="truncate text-xs text-muted-foreground">{row.original.companyType}</p>
        </div>
      </div>
    ),
    enableHiding: false,
  },
  {
    id: "industry",
    accessorKey: "industry",
    header: ({ column }) => <SortableHeader column={column} label="Industry" />,
    cell: ({ getValue }) => (
      <Badge variant="outline" className="whitespace-nowrap">
        {getValue<string>()}
      </Badge>
    ),
    filterFn: (row, columnId, filterValue: string) => {
      if (!filterValue || filterValue === "all") return true;
      return row.getValue<string>(columnId) === filterValue;
    },
  },
  {
    id: "location",
    accessorFn: (row) => `${row.city}, ${row.country}`,
    header: ({ column }) => <SortableHeader column={column} label="Location" />,
    cell: ({ row }) => (
      <div className="text-sm">
        <p className="text-foreground">{row.original.city}</p>
        <p className="text-xs text-muted-foreground">{row.original.country}</p>
      </div>
    ),
    filterFn: (row, _columnId, filterValue: string) => {
      if (!filterValue || filterValue === "all") return true;
      return row.original.country === filterValue;
    },
  },
  {
    id: "contactName",
    accessorKey: "contactName",
    header: ({ column }) => <SortableHeader column={column} label="Contact" />,
    cell: ({ getValue }) => <span className="text-sm text-foreground whitespace-nowrap">{getValue<string>()}</span>,
  },
  {
    id: "leadScore",
    accessorKey: "leadScore",
    header: ({ column }) => <SortableHeader column={column} label="Lead Score" />,
    cell: ({ getValue }) => <ScoreBadge score={getValue<number>()} />,
  },
  {
    id: "rating",
    accessorKey: "rating",
    header: ({ column }) => <SortableHeader column={column} label="Rating" />,
    cell: ({ getValue }) => <RatingStars rating={getValue<number>()} />,
  },
  {
    id: "status",
    accessorKey: "status",
    header: ({ column }) => <SortableHeader column={column} label="Status" />,
    cell: ({ getValue }) => <StatusBadge status={getValue<Lead["status"]>()} />,
    filterFn: (row, columnId, filterValue: string) => {
      if (!filterValue || filterValue === "all") return true;
      return row.getValue<string>(columnId) === filterValue;
    },
  },
  {
    id: "provider",
    accessorKey: "provider",
    header: ({ column }) => <SortableHeader column={column} label="Provider" />,
    cell: ({ getValue }) => <span className="text-xs text-muted-foreground whitespace-nowrap">{getValue<string>()}</span>,
  },
  {
    id: "createdAt",
    accessorKey: "createdAt",
    header: ({ column }) => <SortableHeader column={column} label="Created" />,
    cell: ({ getValue }) => (
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {formatDistanceToNowStrict(new Date(getValue<string>()), { addSuffix: true })}
      </span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => <RowActions lead={row.original} />,
    enableSorting: false,
    enableHiding: false,
    size: 40,
  },
];

export const OPTIONAL_COLUMN_LABELS: Record<string, string> = {
  industry: "Industry",
  location: "Location",
  contactName: "Contact",
  leadScore: "Lead Score",
  rating: "Rating",
  provider: "Provider",
  createdAt: "Created",
};
