"use client";

import { Plus, Minus } from "lucide-react";
import { PinMarker } from "@/components/map/pin-marker";
import { ClusterMarker } from "@/components/map/cluster-marker";
import { LeadPreviewCard } from "@/components/map/lead-preview-card";
import { buildClusters, MAP_CENTER, type PositionedLead } from "@/components/map/map-utils";

export function MapCanvas({
  leads,
  zoomed,
  onToggleZoom,
  radiusPercent,
  hoveredId,
  pinnedId,
  onHover,
  onSelect,
  onDeselect,
}: {
  leads: PositionedLead[];
  zoomed: boolean;
  onToggleZoom: (v: boolean) => void;
  radiusPercent: number;
  hoveredId: string | null;
  pinnedId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
  onDeselect: () => void;
}) {
  const clusters = buildClusters(leads);
  const showClusters = !zoomed && clusters.some((c) => c.count > 1);
  const activeLead = leads.find((l) => l.id === (pinnedId ?? hoveredId)) ?? null;

  return (
    <div
      onClick={onDeselect}
      className="relative min-h-[70vh] w-full overflow-hidden rounded-2xl border border-border bg-grid bg-background"
      style={{
        backgroundImage:
          "radial-gradient(circle at 30% 20%, color-mix(in oklch, var(--color-primary) 10%, transparent), transparent 45%), radial-gradient(circle at 75% 70%, color-mix(in oklch, var(--color-accent) 10%, transparent), transparent 45%)",
      }}
    >
      {/* radius overlay */}
      <div
        className="pointer-events-none absolute rounded-full border border-primary/30 bg-primary/[0.04] transition-all duration-300"
        style={{
          left: `${MAP_CENTER.x}%`,
          top: `${MAP_CENTER.y}%`,
          width: `${radiusPercent}%`,
          height: `${radiusPercent}%`,
          transform: "translate(-50%, -50%)",
        }}
      />
      <div
        className="pointer-events-none absolute size-2 rounded-full bg-primary shadow-[0_0_12px_2px_var(--color-primary)]"
        style={{ left: `${MAP_CENTER.x}%`, top: `${MAP_CENTER.y}%`, transform: "translate(-50%, -50%)" }}
      />

      {showClusters
        ? clusters.map((cluster) =>
            cluster.count > 1 ? (
              <ClusterMarker key={cluster.key} cluster={cluster} onClick={() => onToggleZoom(true)} />
            ) : (
              <PinMarker
                key={cluster.leads[0].id}
                lead={cluster.leads[0]}
                active={cluster.leads[0].id === (hoveredId ?? pinnedId)}
                onHoverStart={() => onHover(cluster.leads[0].id)}
                onHoverEnd={() => onHover(null)}
                onSelect={() => onSelect(cluster.leads[0].id)}
              />
            ),
          )
        : leads.map((lead) => (
            <PinMarker
              key={lead.id}
              lead={lead}
              active={lead.id === (hoveredId ?? pinnedId)}
              onHoverStart={() => onHover(lead.id)}
              onHoverEnd={() => onHover(null)}
              onSelect={() => onSelect(lead.id)}
            />
          ))}

      <LeadPreviewCard lead={activeLead} pinned={!!pinnedId} onClose={onDeselect} />

      {/* zoom control */}
      <div className="absolute bottom-4 right-4 z-20 flex flex-col overflow-hidden rounded-lg border border-border-strong glass-strong shadow-lg">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleZoom(true);
          }}
          className="flex size-9 items-center justify-center text-foreground hover:bg-surface-2"
          aria-label="Zoom in"
        >
          <Plus className="size-4" />
        </button>
        <div className="h-px bg-border" />
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggleZoom(false);
          }}
          className="flex size-9 items-center justify-center text-foreground hover:bg-surface-2"
          aria-label="Zoom out"
        >
          <Minus className="size-4" />
        </button>
      </div>
    </div>
  );
}
