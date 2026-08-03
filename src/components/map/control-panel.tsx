"use client";

import { Sparkles, Radar } from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import * as React from "react";
import { MAP_PROVIDERS, type MapProviderId } from "@/components/map/map-utils";
import { useTopIndustries } from "@/lib/api/queries";

export function ControlPanel({
  radiusKm,
  onRadiusChange,
  provider,
  onProviderChange,
  industry,
  onIndustryChange,
  inViewCount,
  clusterCount,
}: {
  radiusKm: number;
  onRadiusChange: (v: number) => void;
  provider: MapProviderId;
  onProviderChange: (v: MapProviderId) => void;
  industry: string;
  onIndustryChange: (v: string) => void;
  inViewCount: number;
  clusterCount: number;
}) {
  // Real industries present in this organization's leads, not a fixture's list.
  const { data: industriesData } = useTopIndustries();
  const industries = React.useMemo(
    () => (industriesData ?? []).map((i) => i.name).filter(Boolean),
    [industriesData],
  );

  return (
    <div className="glass-strong w-[300px] rounded-2xl border border-border-strong p-4 shadow-2xl">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">Search Radius</p>
        <span className="text-xs font-medium text-muted-foreground">{radiusKm} km</span>
      </div>
      <Slider
        className="mt-3"
        min={5}
        max={150}
        step={5}
        value={[radiusKm]}
        onValueChange={([v]) => onRadiusChange(v)}
      />

      <p className="mt-4 text-xs font-medium text-muted-foreground">Map Provider</p>
      <div className="mt-2 flex gap-1.5">
        {MAP_PROVIDERS.map((p) => (
          <button
            key={p.id}
            onClick={() => onProviderChange(p.id)}
            className={cn(
              "flex-1 rounded-lg border px-2 py-1.5 text-[11px] font-medium transition-colors",
              provider === p.id
                ? "border-primary/40 bg-primary/15 text-primary"
                : "border-border bg-surface-2/60 text-muted-foreground hover:text-foreground",
            )}
          >
            {p.label}
          </button>
        ))}
      </div>

      <p className="mt-4 text-xs font-medium text-muted-foreground">Nearby Industries</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <button
          onClick={() => onIndustryChange("all")}
          className={cn(
            "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
            industry === "all"
              ? "border-primary/40 bg-primary/15 text-primary"
              : "border-border bg-surface-2/60 text-muted-foreground hover:text-foreground",
          )}
        >
          All
        </button>
        {industries.slice(0, 5).map((ind: string) => (
          <button
            key={ind}
            onClick={() => onIndustryChange(ind)}
            className={cn(
              "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
              industry === ind
                ? "border-primary/40 bg-primary/15 text-primary"
                : "border-border bg-surface-2/60 text-muted-foreground hover:text-foreground",
            )}
          >
            {ind}
          </button>
        ))}
      </div>

      <div className="mt-4 flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/[0.06] p-2.5">
        <Sparkles className="mt-0.5 size-3.5 shrink-0 text-primary" />
        <p className="text-[11px] leading-snug text-muted-foreground">
          {clusterCount > 0
            ? `${clusterCount} high-density cluster${clusterCount === 1 ? "" : "s"} found within ${radiusKm}km — ${inViewCount} leads in view.`
            : `No dense clusters nearby — try widening your radius.`}
        </p>
      </div>

      <div className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Radar className="size-3.5" />
        Radius overlay reflects live slider value
      </div>
    </div>
  );
}

export function ResultCountBadge({
  count,
  total,
  loading = false,
}: {
  count: number;
  total: number;
  loading?: boolean;
}) {
  return (
    <Badge variant="primary" className="glass-strong shadow-lg">
      {loading ? "Searching…" : `${count} in view · ${total} mapped`}
    </Badge>
  );
}
