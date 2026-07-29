"use client";

import * as React from "react";
import { Search, Sparkles, ArrowRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PLACEHOLDER_SUGGESTIONS = [
  "Panel Builders in Pune",
  "Electrical Dealers near Mumbai",
  "Industrial Automation OEMs in Ahmedabad",
  "System Integrators in Singapore",
  "EPC Companies in Dubai",
];

const AI_SUGGESTIONS = [
  "Panel Builders in Pune",
  "Electrical Dealers near Mumbai",
  "Industrial Automation OEM in Ahmedabad",
  "System Integrators in Singapore",
  "EPC Companies in Dubai",
  "Manufacturers in Jakarta",
];

export function SearchBar({
  query,
  onQueryChange,
  onSearch,
  isSearching,
}: {
  query: string;
  onQueryChange: (value: string) => void;
  onSearch: () => void;
  isSearching: boolean;
}) {
  const [placeholderIndex, setPlaceholderIndex] = React.useState(0);

  React.useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIndex((i) => (i + 1) % PLACEHOLDER_SUGGESTIONS.length);
    }, 2800);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative rounded-2xl border border-border-strong glass-strong p-5 sm:p-6 overflow-hidden">
      <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />
      <div className="relative">
        <div className="flex items-center gap-2 mb-3">
          <div className="flex size-6 items-center justify-center rounded-md bg-primary/15 border border-primary/20">
            <Sparkles className="size-3.5 text-primary" />
          </div>
          <p className="text-xs font-medium text-muted-foreground">AI-powered lead discovery</p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSearch();
          }}
          className="flex flex-col sm:flex-row gap-3"
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              placeholder={`Try "${PLACEHOLDER_SUGGESTIONS[placeholderIndex]}"`}
              className="h-12 rounded-xl pl-10 pr-3 text-[15px] bg-surface-2/80"
            />
          </div>
          <Button
            type="submit"
            variant="gradient"
            size="lg"
            disabled={isSearching}
            className="h-12 shrink-0 min-w-[140px]"
          >
            {isSearching ? "Searching…" : "Search"}
            {!isSearching && <ArrowRight className="size-4" />}
          </Button>
        </form>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground mr-1">AI suggestions:</span>
          {AI_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onQueryChange(s)}
              className={cn(
                "inline-flex items-center rounded-full border border-border bg-surface-2/60 px-3 py-1 text-xs font-medium text-foreground/80",
                "hover:border-primary/40 hover:bg-primary/10 hover:text-primary transition-colors cursor-pointer",
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
