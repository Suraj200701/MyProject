"use client";

import { Globe, Layers, Map as MapIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Where a search should look for leads.
 *
 * Mirrors the backend's `SearchMode`. Omitting the mode entirely is also valid
 * on the wire — that preserves the pre-feature behaviour for existing API
 * clients — but the UI always sends one of these three.
 */
export type LeadSource = "map" | "api" | "auto";

const OPTIONS: {
  value: LeadSource;
  label: string;
  hint: string;
  icon: typeof MapIcon;
}[] = [
  {
    value: "map",
    label: "Map — Public Data",
    hint: "OpenStreetMap and Overpass. No API key, no credentials.",
    icon: MapIcon,
  },
  {
    value: "api",
    label: "API — Configured Providers",
    hint: "Only providers you have credentials for.",
    icon: Globe,
  },
  {
    value: "auto",
    label: "Auto — API → Map fallback",
    hint: "Tries your providers first; uses public map data if they return nothing.",
    icon: Layers,
  },
];

/**
 * Native radios rather than a styled listbox: this is a small, mutually
 * exclusive choice, so arrow-key navigation, form semantics and screen-reader
 * announcements come for free and correctly.
 */
export function LeadSourceSelector({
  value,
  onChange,
  disabled = false,
}: {
  value: LeadSource;
  onChange: (next: LeadSource) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="mb-2 text-sm font-medium text-foreground">Lead Source</legend>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {OPTIONS.map((option) => {
          const Icon = option.icon;
          const active = value === option.value;
          return (
            <label
              key={option.value}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors",
                "hover:bg-accent/50 focus-within:ring-2 focus-within:ring-ring",
                active ? "border-primary bg-primary/5" : "border-border bg-card",
                disabled && "cursor-not-allowed opacity-60",
              )}
            >
              <input
                type="radio"
                name="lead-source"
                value={option.value}
                checked={active}
                onChange={() => onChange(option.value)}
                className="mt-1 size-4 accent-primary"
              />
              <span className="min-w-0">
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  <Icon className="size-3.5 shrink-0" aria-hidden />
                  {option.label}
                </span>
                <span className="mt-0.5 block text-xs text-muted-foreground">{option.hint}</span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
