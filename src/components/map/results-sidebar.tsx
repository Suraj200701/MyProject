"use client";

import { Building2, Star } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { scoreTone, type PositionedLead } from "@/components/map/map-utils";

export function ResultsSidebar({
  leads,
  activeId,
  onHover,
  onSelect,
}: {
  leads: PositionedLead[];
  activeId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <p className="text-sm font-semibold">Leads in View</p>
        <p className="text-xs text-muted-foreground">{leads.length} results</p>
      </div>
      <div className="flex-1 overflow-y-auto">
        {leads.map((lead) => (
          <button
            key={lead.id}
            onMouseEnter={() => onHover(lead.id)}
            onMouseLeave={() => onHover(null)}
            onClick={() => onSelect(lead.id)}
            className={cn(
              "flex w-full items-start gap-2.5 border-b border-border/60 px-4 py-3 text-left transition-colors hover:bg-surface-2/60",
              activeId === lead.id && "bg-surface-2",
            )}
          >
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
              <Building2 className="size-3.5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium leading-tight">{lead.company}</p>
              <p className="truncate text-xs text-muted-foreground">{lead.city}</p>
              <div className="mt-1 flex items-center gap-1.5">
                <Badge variant={scoreTone(lead.leadScore)} className="px-1.5 py-0 text-[10px]">
                  {lead.leadScore}
                </Badge>
                <span className="inline-flex items-center gap-0.5 text-[11px] text-muted-foreground">
                  <Star className="size-2.5 fill-warning text-warning" />
                  {lead.rating.toFixed(1)}
                </span>
                <span className="ml-auto text-[10px] text-muted-foreground">{lead.distanceKm}km</span>
              </div>
            </div>
          </button>
        ))}
        {leads.length === 0 && (
          <p className="px-4 py-8 text-center text-xs text-muted-foreground">
            No leads within this radius. Try widening the search.
          </p>
        )}
      </div>
    </div>
  );
}
