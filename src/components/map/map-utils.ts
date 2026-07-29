import { mockLeads } from "@/lib/mock-data";
import type { Lead } from "@/lib/types";

/** A lead positioned on the mock map canvas (0-100 percent coordinates). */
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

export const MAP_INDUSTRIES = Array.from(new Set(mockLeads.map((l) => l.industry))).sort();

const lats = mockLeads.map((l) => l.lat);
const lngs = mockLeads.map((l) => l.lng);
const MIN_LAT = Math.min(...lats);
const MAX_LAT = Math.max(...lats);
const MIN_LNG = Math.min(...lngs);
const MAX_LNG = Math.max(...lngs);
const CENTER_LAT = lats.reduce((a, b) => a + b, 0) / lats.length;
const CENTER_LNG = lngs.reduce((a, b) => a + b, 0) / lngs.length;

/** Pad-and-clamp linear scaling from a lat/lng pair into 0-100 canvas percent space. */
function project(lat: number, lng: number): { x: number; y: number } {
  const rawX = MAX_LNG === MIN_LNG ? 50 : ((lng - MIN_LNG) / (MAX_LNG - MIN_LNG)) * 100;
  const rawY = MAX_LAT === MIN_LAT ? 50 : ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * 100;
  return { x: 4 + (rawX / 100) * 92, y: 4 + (rawY / 100) * 92 };
}

/**
 * Cosmetic pseudo-distance in "km" from the fixed mock search center.
 * Scaled down (0.15x) from the raw lat/lng delta so the spread of mock leads
 * (generated across several degrees for map canvas variety) maps onto the
 * 5-150km radius slider range instead of the true ~100s-1000s km spread.
 */
function pseudoDistanceKm(lat: number, lng: number): number {
  const dLat = (lat - CENTER_LAT) * 111;
  const dLng = (lng - CENTER_LNG) * 111 * Math.cos((CENTER_LAT * Math.PI) / 180);
  return Math.round(Math.sqrt(dLat * dLat + dLng * dLng) * 0.15);
}

export const MAP_CENTER = project(CENTER_LAT, CENTER_LNG);

let cachedPositionedLeads: PositionedLead[] | null = null;

export function getPositionedLeads(): PositionedLead[] {
  if (cachedPositionedLeads) return cachedPositionedLeads;
  cachedPositionedLeads = mockLeads.map((lead) => {
    const { x, y } = project(lead.lat, lead.lng);
    return { ...lead, x, y, distanceKm: pseudoDistanceKm(lead.lat, lead.lng) };
  });
  return cachedPositionedLeads;
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
    const avgScore = Math.round(bucketLeads.reduce((sum, l) => sum + l.leadScore, 0) / bucketLeads.length);
    return { key, x, y, count: bucketLeads.length, avgScore, leads: bucketLeads };
  });
}
