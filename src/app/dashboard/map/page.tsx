"use client";

import * as React from "react";
import { MapPinOff } from "lucide-react";

import { PageHeader } from "@/components/shared/page-header";
import { MapCanvas } from "@/components/map/map-canvas";
import { ControlPanel, ResultCountBadge } from "@/components/map/control-panel";
import { ResultsSidebar } from "@/components/map/results-sidebar";
import { EmptyState } from "@/components/shared/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  buildClusters,
  computeBounds,
  positionLeads,
  type MapProviderId,
} from "@/components/map/map-utils";
import { hasCoordinates } from "@/lib/api/mappers";
import { useLeads, useNearbyLeads } from "@/lib/api/queries";

/**
 * Map Search, backed by `POST /map/nearby-leads`.
 *
 * How it works now
 * ----------------
 * 1. A page of leads is fetched to find the organization's geographic centre —
 *    the radius search needs an origin, and centring on the leads the user
 *    actually has is more useful than a fixed point.
 * 2. That centre plus the radius slider and industry filter go to
 *    `POST /map/nearby-leads`, which does the distance filtering **in SQL with
 *    real haversine maths**. The distances shown are therefore real kilometres.
 * 3. The returned leads are projected into the canvas using bounds computed from
 *    those same leads.
 *
 * Previously the whole thing was client-side over a fixture, with a
 * "pseudo-distance" scaled by an arbitrary 0.15x so the invented spread would
 * land inside the slider's 5–150km range.
 *
 * The provider toggle (Google / Mappls / OpenStreetMap) is retained as-is: it is
 * cosmetic in both the frontend and the backend — `nearby-leads` is pure
 * database maths and consults no map provider — so it selects a label only.
 */
export default function MapSearchPage() {
  const [radiusKm, setRadiusKm] = React.useState(60);
  const [provider, setProvider] = React.useState<MapProviderId>("google");
  const [industry, setIndustry] = React.useState("all");
  const [zoomed, setZoomed] = React.useState(false);
  const [hoveredId, setHoveredId] = React.useState<string | null>(null);
  const [pinnedId, setPinnedId] = React.useState<string | null>(null);

  // Enough leads to establish a sensible centre without fetching everything.
  const { data: leadsPage, isPending: leadsPending } = useLeads({ page_size: 100 });
  const locatedLeads = React.useMemo(
    () => (leadsPage?.items ?? []).filter(hasCoordinates),
    [leadsPage],
  );

  const originBounds = React.useMemo(() => computeBounds(locatedLeads), [locatedLeads]);

  const nearbyParams = React.useMemo(
    () =>
      originBounds
        ? {
            lat: originBounds.centerLat,
            lng: originBounds.centerLng,
            radius_km: radiusKm,
            industry: industry !== "all" ? industry : undefined,
          }
        : null,
    [originBounds, radiusKm, industry],
  );

  const { data: nearby, isPending: nearbyPending } = useNearbyLeads(nearbyParams);

  // Project using the bounds of the leads actually being displayed, so the pins
  // fill the canvas rather than clustering in a corner.
  const visibleLeads = React.useMemo(() => {
    const rows = nearby ?? [];
    const bounds = computeBounds(rows) ?? originBounds;
    if (!bounds) return [];
    return positionLeads(rows, bounds);
  }, [nearby, originBounds]);

  const clusters = React.useMemo(() => buildClusters(visibleLeads), [visibleLeads]);
  const clusterCount = clusters.filter((c) => c.count > 3).length;

  const radiusPercent = 6 + ((radiusKm - 5) / (150 - 5)) * 84;
  const isPending = leadsPending || (!!nearbyParams && nearbyPending);

  if (leadsPending) {
    return (
      <div>
        <PageHeader
          title="Map Search"
          description="Discover nearby leads visually, cluster by density, and refine by radius."
        />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
          <Skeleton className="order-2 h-[70vh] rounded-xl lg:order-1" />
          <Skeleton className="order-1 h-[70vh] rounded-xl lg:order-2" />
        </div>
      </div>
    );
  }

  // No lead has coordinates: say so, rather than rendering an empty canvas that
  // looks like a rendering failure.
  if (!originBounds) {
    return (
      <div>
        <PageHeader
          title="Map Search"
          description="Discover nearby leads visually, cluster by density, and refine by radius."
        />
        <EmptyState
          icon={MapPinOff}
          title="No mapped leads yet"
          description="None of your leads have coordinates. Leads sourced via Google Places or Mappls include them automatically; for imported leads, geocode them first."
        />
      </div>
    );
  }

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
              <ResultCountBadge
                count={visibleLeads.length}
                total={locatedLeads.length}
                loading={isPending}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
