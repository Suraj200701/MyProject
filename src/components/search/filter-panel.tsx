"use client";

import * as React from "react";
import { SlidersHorizontal, Star } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { ChipInput } from "@/components/search/chip-input";
import { useCountryAnalytics, useProviders, useTopIndustries } from "@/lib/api/queries";
import type { SearchFilters } from "@/components/search/types";

/**
 * Company types the backend recognises.
 *
 * Unlike industries/countries/providers there is no endpoint that enumerates
 * distinct company types, so this stays a static list — it is a fixed set of
 * legal forms, not data derived from the lead table. Kept as UI configuration
 * rather than deleted, since a free-text field here would be worse.
 */
const COMPANY_TYPES = ["Private Ltd", "Public Ltd", "LLP", "Partnership", "Proprietorship"];

export function FilterPanel({
  filters,
  onChange,
}: {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}) {
  // Options come from the analytics/provider endpoints, so the dropdowns reflect
  // the organization's actual data instead of a fixture's vocabulary.
  const { data: industriesData } = useTopIndustries();
  const { data: countriesData } = useCountryAnalytics();
  const { data: providersData } = useProviders();

  const industries = React.useMemo(
    () => Array.from(new Set((industriesData ?? []).map((i) => i.name).filter(Boolean))).sort(),
    [industriesData],
  );
  const countries = React.useMemo(
    () => Array.from(new Set((countriesData ?? []).map((c) => c.country).filter(Boolean))).sort(),
    [countriesData],
  );
  const providers = React.useMemo(
    () => Array.from(new Set((providersData ?? []).map((p) => p.name))).sort(),
    [providersData],
  );
  const companyTypes = COMPANY_TYPES;

  function update<K extends keyof SearchFilters>(key: K, value: SearchFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <Card className="glass">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-[13px] uppercase tracking-wide text-muted-foreground">
          <SlidersHorizontal className="size-3.5" />
          Filters
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 pt-4">
        <div className="grid grid-cols-1 gap-4">
          <div className="space-y-1.5">
            <Label>Industry</Label>
            <Select value={filters.industry} onValueChange={(v) => update("industry", v)}>
              <SelectTrigger>
                <SelectValue placeholder="All industries" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All industries</SelectItem>
                {industries.map((i) => (
                  <SelectItem key={i} value={i}>
                    {i}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Country</Label>
            <Select value={filters.country} onValueChange={(v) => update("country", v)}>
              <SelectTrigger>
                <SelectValue placeholder="All countries" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All countries</SelectItem>
                {countries.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Provider</Label>
            <Select value={filters.provider} onValueChange={(v) => update("provider", v)}>
              <SelectTrigger>
                <SelectValue placeholder="All providers" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All providers</SelectItem>
                {providers.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label>Company type</Label>
            <Select value={filters.companyType} onValueChange={(v) => update("companyType", v)}>
              <SelectTrigger>
                <SelectValue placeholder="All company types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All company types</SelectItem>
                {companyTypes.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="flex items-center gap-1.5">
              <Star className="size-3.5 text-warning" />
              Minimum rating
            </Label>
            <span className="text-xs font-medium text-muted-foreground">
              {filters.minRating.toFixed(1)}+
            </span>
          </div>
          <Slider
            value={[filters.minRating]}
            min={0}
            max={5}
            step={0.5}
            onValueChange={([v]) => update("minRating", v)}
          />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Lead score range</Label>
            <span className="text-xs font-medium text-muted-foreground">
              {filters.scoreRange[0]} – {filters.scoreRange[1]}
            </span>
          </div>
          <Slider
            value={filters.scoreRange}
            min={0}
            max={100}
            step={5}
            onValueChange={(v) => update("scoreRange", [v[0], v[1]] as [number, number])}
          />
        </div>

        <div className="space-y-1.5">
          <Label>Cities</Label>
          <ChipInput
            values={filters.cities}
            onChange={(v) => update("cities", v)}
            placeholder="Add a city and press Enter"
          />
        </div>

        <div className="space-y-1.5">
          <Label>Keywords</Label>
          <ChipInput
            values={filters.keywords}
            onChange={(v) => update("keywords", v)}
            placeholder="Add a keyword and press Enter"
          />
        </div>
      </CardContent>
    </Card>
  );
}
