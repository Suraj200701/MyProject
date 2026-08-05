"use client";

import * as React from "react";
import { Download, Loader2, MapPin, RotateCcw, Search, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { MapView } from "@/components/search/map-view";
import { errorMessage } from "@/lib/api/client";
import { useExtractMapResults, useImportMapResults } from "@/lib/api/queries";
import type { MapResult } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * Map Mode: extract publicly available businesses, review them, import the ones
 * you want.
 *
 * Data comes from OpenStreetMap (Nominatim) and Overpass via the backend. Both
 * publish openly licensed data and permit programmatic access, which is why this
 * needs no API key and no browser extension. Nothing here reads another map
 * provider's rendered page — that would mean working around its terms and its
 * anti-bot measures.
 *
 * Two steps on purpose: extraction saves nothing, so the user sees what was found
 * before any of it becomes a lead.
 */
export function MapMode() {
  const [keyword, setKeyword] = React.useState("");
  const [location, setLocation] = React.useState("");
  const [results, setResults] = React.useState<MapResult[] | null>(null);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [focused, setFocused] = React.useState<string | null>(null);
  const [blocked, setBlocked] = React.useState<string | null>(null);

  const extract = useExtractMapResults();
  const importResults = useImportMapResults();
  const router = useRouter();

  const canExtract = keyword.trim().length > 0 && location.trim().length > 0;

  function runExtraction() {
    if (!canExtract || extract.isPending) return;
    setResults(null);
    setSelected(new Set());
    setBlocked(null);

    extract.mutate(
      { query: keyword.trim(), location: location.trim() },
      {
        onSuccess: (data) => {
          setResults(data.results);
          setBlocked(data.blocked_reason);
          // Pre-select everything: the common case is "import all of it", and
          // the user can uncheck. Nothing is saved until Import is pressed.
          setSelected(new Set(data.results.map((r) => r.id)));

          if (data.results.length === 0 && !data.blocked_reason) {
            toast.info("No public results for that keyword and location.", {
              description: "Try a broader keyword, or a nearby larger city.",
            });
          }
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  }

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function importSelected() {
    if (!results || selected.size === 0 || importResults.isPending) return;
    const chosen = results.filter((r) => selected.has(r.id));

    importResults.mutate(chosen, {
      onSuccess: (outcome) => {
        const parts = [`${outcome.imported} lead${outcome.imported === 1 ? "" : "s"} imported`];
        if (outcome.duplicates > 0) {
          parts.push(`${outcome.duplicates} already in your database`);
        }
        toast.success(parts.join(" · "), {
          description:
            outcome.imported > 0
              ? "Scored and saved. They behave like any other lead."
              : "Nothing new to add.",
          action:
            outcome.imported > 0
              ? { label: "View leads", onClick: () => router.push("/dashboard/leads") }
              : undefined,
        });
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  }

  const allSelected = results !== null && results.length > 0 && selected.size === results.length;
  const positioned = (results ?? []).filter((r) => r.latitude !== null).length;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <div className="space-y-1.5">
          <Label htmlFor="map-keyword">Keyword</Label>
          <Input
            id="map-keyword"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runExtraction()}
            placeholder="Electrical Panel"
            disabled={extract.isPending}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="map-location">Location</Label>
          <Input
            id="map-location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runExtraction()}
            placeholder="Bhopal"
            disabled={extract.isPending}
          />
        </div>
        <Button onClick={runExtraction} disabled={!canExtract || extract.isPending}>
          {extract.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Extracting…
            </>
          ) : (
            <>
              <Search className="size-4" />
              Open Map
            </>
          )}
        </Button>
      </div>

      {/* A location is required because Overpass searches a radius around a
          place — saying so up front beats a rejected request. */}
      {!canExtract && (
        <p className="text-xs text-muted-foreground">
          Both a keyword and a location are needed: results are gathered within a radius
          around the place you name.
        </p>
      )}

      {blocked && (
        <div className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
          <div>
            <p className="font-medium">The map provider didn&apos;t answer.</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{blocked}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Overpass is a free shared service and throttles under load. Retry in a moment,
              or switch to API mode.
            </p>
            <Button size="sm" variant="outline" className="mt-2" onClick={runExtraction}>
              <RotateCcw className="size-3.5" />
              Retry
            </Button>
          </div>
        </div>
      )}

      {results !== null && results.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <MapView
              results={results}
              selectedId={focused}
              onSelect={setFocused}
              className="h-[420px] w-full overflow-hidden rounded-xl border border-border"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              {positioned} of {results.length} results have coordinates. Map data ©{" "}
              <a
                href="https://www.openstreetmap.org/copyright"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                OpenStreetMap
              </a>{" "}
              contributors, ODbL.
            </p>
          </div>

          <div className="lg:col-span-2">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-sm font-medium">
                Found <span className="tabular-nums">{results.length}</span> public results
              </p>
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  setSelected(allSelected ? new Set() : new Set(results.map((r) => r.id)))
                }
              >
                {allSelected ? "Clear" : "Select all"}
              </Button>
            </div>

            <ul className="max-h-[360px] space-y-1.5 overflow-y-auto pr-1">
              {results.map((result) => (
                <li key={result.id}>
                  <div
                    className={cn(
                      "flex items-start gap-2 rounded-lg border p-2.5 text-left transition-colors",
                      focused === result.id
                        ? "border-primary bg-primary/5"
                        : "border-border bg-card hover:bg-accent/40",
                    )}
                  >
                    <Checkbox
                      checked={selected.has(result.id)}
                      onCheckedChange={() => toggle(result.id)}
                      aria-label={`Select ${result.company_name ?? "result"}`}
                      className="mt-0.5"
                    />
                    <button
                      type="button"
                      onClick={() => setFocused(result.id)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <p className="truncate text-sm font-medium">
                        {result.company_name ?? "Unnamed location"}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {[result.category, result.address].filter(Boolean).join(" · ") || "—"}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-1">
                        {result.phone && (
                          <Badge variant="outline" className="text-[10px]">
                            {result.phone}
                          </Badge>
                        )}
                        {result.website && (
                          <Badge variant="outline" className="text-[10px]">
                            website
                          </Badge>
                        )}
                        {result.source_provider && (
                          <Badge variant="outline" className="text-[10px]">
                            {result.source_provider}
                          </Badge>
                        )}
                      </div>
                    </button>
                  </div>
                </li>
              ))}
            </ul>

            <Button
              className="mt-3 w-full"
              onClick={importSelected}
              disabled={selected.size === 0 || importResults.isPending}
            >
              {importResults.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Importing…
                </>
              ) : (
                <>
                  <Download className="size-4" />
                  Import {selected.size} selected lead{selected.size === 1 ? "" : "s"}
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {results !== null && results.length === 0 && !blocked && (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border p-10 text-center">
          <MapPin className="size-5 text-muted-foreground" aria-hidden />
          <p className="text-sm font-medium">No public results found</p>
          <p className="max-w-sm text-xs text-muted-foreground">
            OpenStreetMap is volunteer-mapped, so coverage varies by area and category. A
            broader keyword — &ldquo;hospital&rdquo; rather than a brand name — usually helps.
          </p>
        </div>
      )}
    </div>
  );
}
