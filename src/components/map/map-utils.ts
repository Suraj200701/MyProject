import type { Lead } from "@/lib/types";

/** A lead positioned on the map canvas (0-100 percent coordinates). */
export interface PositionedLead extends Lead {
  x: number;
  y: number;
  distanceKm: number;
}

export interface MapCluster {
  key: string;
  x: number;
  y: number;
  count: number;
  avgScore: number;
  leads: PositionedLead[];
}

export const MAP_PROVIDERS = [
  { id: "google", label: "Google Maps" },
  { id: "mappls", label: "Mappls" },
  { id: "osm", label: "OpenStreetMap" },
] as const;

export type MapProviderId = (typeof MAP_PROVIDERS)[number]["id"];

export interface GeoBounds {
  minLat: number;
  maxLat: number;
  minLng: number;
  maxLng: number;
  centerLat: number;
  centerLng: number;
}

/**
 * Geographic bounds of a set of leads.
 *
 * Computed from real data at call time. This module previously derived its bounds
 * and centre from the fixture **at import time**, so the projection was
 * calibrated to invented coordinates and could never fit a real lead set.
 *
 * Leads without coordinates are excluded: the mapper marks those `NaN` rather
 * than 0/0, which would otherwise drop a pin in the Gulf of Guinea.
 */
export function computeBounds(leads: Lead[]): GeoBounds | null {
  const located = leads.filter((l) => Number.isFinite(l.lat) && Number.isFinite(l.lng));
  if (located.length === 0) return null;

  const lats = located.map((l) => l.lat);
  const lngs = located.map((l) => l.lng);
  return {
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
    minLng: Math.min(...lngs),
    maxLng: Math.max(...lngs),
    centerLat: lats.reduce((a, b) => a + b, 0) / lats.length,
    centerLng: lngs.reduce((a, b) => a + b, 0) / lngs.length,
  };
}

/** Pad-and-clamp linear scaling from a lat/lng pair into 0-100 canvas percent space. */
export function project(lat: number, lng: number, bounds: GeoBounds): { x: number; y: number } {
  const { minLat, maxLat, minLng, maxLng } = bounds;
  const rawX = maxLng === minLng ? 50 : ((lng - minLng) / (maxLng - minLng)) * 100;
  // Latitude increases northward but canvas y increases downward, hence the flip.
  const rawY = maxLat === minLat ? 50 : ((maxLat - lat) / (maxLat - minLat)) * 100;
  return { x: 4 + (rawX / 100) * 92, y: 4 + (rawY / 100) * 92 };
}

/**
 * Positions leads on the canvas.
 *
 * `distanceKm` is expected to already be on each lead — it comes from
 * `POST /map/nearby-leads`, which computes real haversine distance server-side.
 * The previous version invented it from a lat/lng delta scaled by an arbitrary
 * 0.15x so the fixture's spread would fit the radius slider's range.
 */
export function positionLeads(
  leads: (Lead & { distanceKm?: number })[],
  bounds: GeoBounds,
): PositionedLead[] {
  return leads
    .filter((l) => Number.isFinite(l.lat) && Number.isFinite(l.lng))
    .map((lead) => {
      const { x, y } = project(lead.lat, lead.lng, bounds);
      return { ...lead, x, y, distanceKm: lead.distanceKm ?? 0 };
    });
}

export function mapCenter(bounds: GeoBounds): { x: number; y: number } {
  return project(bounds.centerLat, bounds.centerLng, bounds);
}

export function scoreTone(score: number): "success" | "warning" | "danger" {
  if (score >= 80) return "success";
  if (score >= 60) return "warning";
  return "danger";
}

/** Bins leads into a coarse grid so nearby pins collapse into a single cluster badge. */
export function buildClusters(leads: PositionedLead[], cols = 6, rows = 5): MapCluster[] {
  const cellW = 100 / cols;
  const cellH = 100 / rows;
  const bins = new Map<string, PositionedLead[]>();

  for (const lead of leads) {
    const cx = Math.min(cols - 1, Math.floor(lead.x / cellW));
    const cy = Math.min(rows - 1, Math.floor(lead.y / cellH));
    const key = `${cx}-${cy}`;
    const bucket = bins.get(key);
    if (bucket) bucket.push(lead);
    else bins.set(key, [lead]);
  }

  return Array.from(bins.entries()).map(([key, bucketLeads]) => {
    const x = bucketLeads.reduce((sum, l) => sum + l.x, 0) / bucketLeads.length;
    const y = bucketLeads.reduce((sum, l) => sum + l.y, 0) / bucketLeads.length;
    const avgScore = Math.round(
      bucketLeads.reduce((sum, l) => sum + l.leadScore, 0) / bucketLeads.length,
    );
    return { key, x, y, count: bucketLeads.length, avgScore, leads: bucketLeads };
  });
}
