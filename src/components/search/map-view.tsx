"use client";

import * as React from "react";
import type { Map as LeafletMap, Marker } from "leaflet";

import "leaflet/dist/leaflet.css";

import type { MapResult } from "@/lib/api/types";

/**
 * Leaflet map showing extracted public map results.
 *
 * Leaflet is imported dynamically inside an effect because it touches `window`
 * at module scope, which throws during Next's server render.
 *
 * Markers use `divIcon` rather than Leaflet's default icon. The default pulls
 * `marker-icon.png` from a path Leaflet derives from its own stylesheet URL,
 * which bundlers rewrite — the classic result is a map full of broken images.
 * An inline SVG has no asset to resolve and themes with the rest of the app.
 *
 * Attribution is not optional: OpenStreetMap data is ODbL-licensed and the tile
 * service requires credit, so `attributionControl` stays on.
 */
export function MapView({
  results,
  selectedId,
  onSelect,
  className,
}: {
  results: MapResult[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  className?: string;
}) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const mapRef = React.useRef<LeafletMap | null>(null);
  const markersRef = React.useRef<Map<string, Marker>>(new Map());
  // Held in a ref so the marker effect does not re-run (and rebuild every
  // marker) just because the parent passed a new callback identity. Written in
  // an effect rather than during render: mutating a ref while rendering is what
  // `react-hooks/refs` forbids, and it is genuinely unsafe under concurrent
  // rendering, where a render can be thrown away.
  const onSelectRef = React.useRef(onSelect);
  React.useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  const positioned = React.useMemo(
    () => results.filter((r) => r.latitude !== null && r.longitude !== null),
    [results],
  );

  // Create the map once.
  React.useEffect(() => {
    let cancelled = false;
    let created: LeafletMap | null = null;

    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !containerRef.current || mapRef.current) return;

      created = L.map(containerRef.current, {
        center: [22.9734, 78.6569], // Geographic centre of India — a neutral start.
        zoom: 5,
        scrollWheelZoom: true,
      });

      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(created);

      mapRef.current = created;
    })();

    const markers = markersRef.current;
    return () => {
      cancelled = true;
      // `created` may still be null if the dynamic import lost the race.
      const map = mapRef.current ?? created;
      map?.remove();
      mapRef.current = null;
      markers.clear();
    };
  }, []);

  // Re-render markers whenever the result set changes.
  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      const L = (await import("leaflet")).default;
      const map = mapRef.current;
      if (cancelled || !map) return;

      for (const marker of markersRef.current.values()) marker.remove();
      markersRef.current.clear();

      if (positioned.length === 0) return;

      for (const result of positioned) {
        const icon = L.divIcon({
          className: "",
          html:
            '<span style="display:block;width:18px;height:18px;border-radius:9999px;' +
            "background:var(--color-primary,#4f46e5);border:2px solid #fff;" +
            'box-shadow:0 1px 4px rgba(0,0,0,.4)"></span>',
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        });

        const marker = L.marker([result.latitude as number, result.longitude as number], { icon })
          .addTo(map)
          // Escaped by Leaflet? No — bindPopup accepts HTML, so anything
          // interpolated here must be text-only. `textContent` on a built node
          // avoids hand-rolling escaping for names that contain & or <.
          .bindPopup(popupNode(result));

        marker.on("click", () => onSelectRef.current?.(result.id));
        markersRef.current.set(result.id, marker);
      }

      const bounds = L.latLngBounds(
        positioned.map((r) => [r.latitude as number, r.longitude as number]),
      );
      map.fitBounds(bounds, { padding: [32, 32], maxZoom: 16 });
    })();

    return () => {
      cancelled = true;
    };
  }, [positioned]);

  // Focus the marker for the row the user picked in the sidebar.
  React.useEffect(() => {
    if (!selectedId) return;
    const marker = markersRef.current.get(selectedId);
    const map = mapRef.current;
    if (!marker || !map) return;
    map.panTo(marker.getLatLng());
    marker.openPopup();
  }, [selectedId]);

  return (
    <div
      ref={containerRef}
      role="application"
      aria-label="Map of public results"
      className={className}
    />
  );
}

/** Builds a popup as DOM so business names are inserted as text, never HTML. */
function popupNode(result: MapResult): HTMLElement {
  const wrap = document.createElement("div");
  wrap.style.minWidth = "160px";

  const name = document.createElement("strong");
  name.textContent = result.company_name ?? "Unnamed";
  wrap.appendChild(name);

  for (const line of [result.category, result.address, result.phone]) {
    if (!line) continue;
    const p = document.createElement("div");
    p.style.fontSize = "12px";
    p.textContent = line;
    wrap.appendChild(p);
  }

  if (result.website) {
    const a = document.createElement("a");
    a.href = result.website;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.style.fontSize = "12px";
    a.textContent = "Website";
    wrap.appendChild(a);
  }

  return wrap;
}
