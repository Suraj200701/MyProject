"use client";

import * as React from "react";
import { PageHeader } from "@/components/shared/page-header";
import { MapCanvas } from "@/components/map/map-canvas";
import { ControlPanel, ResultCountBadge } from "@/components/map/control-panel";
import { ResultsSidebar } from "@/components/map/results-sidebar";
import { getPositionedLeads, buildClusters, type MapProviderId } from "@/components/map/map-utils";

export default function MapSearchPage() {
  const allLeads = React.useMemo(() => getPositionedLeads(), []);

  const [radiusKm, setRadiusKm] = React.useState(60);
  const [provider, setProvider] = React.useState<MapProviderId>("google");
  const [industry, setIndustry] = React.useState("all");
  const [zoomed, setZoomed] = React.useState(false);
  const [hoveredId, setHoveredId] = React.useState<string | null>(null);
  const [pinnedId, setPinnedId] = React.useState<string | null>(null);

  const radiusPercent = 6 + ((radiusKm - 5) / (150 - 5)) * 84;

  const visibleLeads = React.useMemo(() => {
    return allLeads.filter((lead) => {
      if (lead.distanceKm > radiusKm) return false;
      if (industry !== "all" && lead.industry !== industry) return false;
      return true;
    });
  }, [allLeads, radiusKm, industry]);

  const clusters = React.useMemo(() => buildClusters(visibleLeads), [visibleLeads]);
  const clusterCount = clusters.filter((c) => c.count > 3).length;

  return (
    <div>
      <PageHeader
        title="Map Search"
        description="Discover nearby leads visually, cluster by density, and refine by radius."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        <div className="order-2 h-[70vh] lg:order-1">
          <ResultsSidebar
            leads={visibleLeads}
            activeId={hoveredId ?? pinnedId}
            onHover={setHoveredId}
            onSelect={(id) => setPinnedId(id)}
          />
        </div>

        <div className="relative order-1 lg:order-2">
          <MapCanvas
            leads={visibleLeads}
            zoomed={zoomed}
            onToggleZoom={setZoomed}
            radiusPercent={radiusPercent}
            hoveredId={hoveredId}
            pinnedId={pinnedId}
            onHover={setHoveredId}
            onSelect={(id) => setPinnedId(id)}
            onDeselect={() => setPinnedId(null)}
          />

          <div className="pointer-events-none absolute inset-4 z-20 flex items-start justify-between">
            <div className="pointer-events-auto">
              <ControlPanel
                radiusKm={radiusKm}
                onRadiusChange={setRadiusKm}
                provider={provider}
                onProviderChange={setProvider}
                industry={industry}
                onIndustryChange={setIndustry}
                inViewCount={visibleLeads.length}
                clusterCount={clusterCount}
              />
            </div>
            <div className="pointer-events-auto">
              <ResultCountBadge count={visibleLeads.length} total={allLeads.length} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
