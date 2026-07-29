"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PageHeader } from "@/components/shared/page-header";
import { SearchBar } from "@/components/search/search-bar";
import { FilterPanel } from "@/components/search/filter-panel";
import { SearchIdle } from "@/components/search/search-idle";
import { SearchProgress } from "@/components/search/search-progress";
import { ResultsGrid } from "@/components/search/results-grid";
import { SearchTimeline, type LiveSearchEntry } from "@/components/search/search-timeline";
import { defaultFilters, type ProviderRun, type SearchFilters, type SearchStage } from "@/components/search/types";
import { mockLeads, searchHistory } from "@/lib/mock-data";
import type { Lead } from "@/lib/types";

const PROVIDER_NAMES = ["Google Places", "IndiaMART", "JustDial", "Mappls"];

function delay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

function matchesQuery(lead: Lead, query: string) {
  if (!query) return true;
  const haystack = `${lead.company} ${lead.industry} ${lead.city} ${lead.country} ${lead.tags.join(" ")}`.toLowerCase();
  if (haystack.includes(query)) return true;
  const words = query.split(/\s+/).filter((w) => w.length >= 3);
  return words.some((w) => haystack.includes(w));
}

function computeResults(query: string, filters: SearchFilters): Lead[] {
  const q = query.trim().toLowerCase();

  const filtered = mockLeads.filter((lead) => {
    if (filters.industry !== "all" && lead.industry !== filters.industry) return false;
    if (filters.country !== "all" && lead.country !== filters.country) return false;
    if (filters.provider !== "all" && lead.provider !== filters.provider) return false;
    if (filters.companyType !== "all" && lead.companyType !== filters.companyType) return false;
    if (lead.rating < filters.minRating) return false;
    if (lead.leadScore < filters.scoreRange[0] || lead.leadScore > filters.scoreRange[1]) return false;
    if (
      filters.cities.length > 0 &&
      !filters.cities.some((c) => lead.city.toLowerCase().includes(c.toLowerCase()))
    ) {
      return false;
    }
    if (filters.keywords.length > 0) {
      const hay = `${lead.company} ${lead.industry} ${lead.tags.join(" ")} ${lead.aiSummary}`.toLowerCase();
      if (!filters.keywords.some((k) => hay.includes(k.toLowerCase()))) return false;
    }
    return matchesQuery(lead, q);
  });

  const ranked = [...filtered].sort((a, b) => b.leadScore - a.leadScore);

  if (ranked.length > 0) {
    return ranked.slice(0, 24);
  }

  // Mock fallback: nothing matched meaningfully, surface a reasonable sample instead of an empty grid.
  const shuffled = [...mockLeads].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, 12 + Math.floor(Math.random() * 6));
}

export default function SearchPage() {
  const [query, setQuery] = React.useState("");
  const [filters, setFilters] = React.useState<SearchFilters>(defaultFilters);
  const [stage, setStage] = React.useState<SearchStage>("idle");
  const [providers, setProviders] = React.useState<ProviderRun[]>([]);
  const [leadsFound, setLeadsFound] = React.useState(0);
  const [elapsedMs, setElapsedMs] = React.useState(0);
  const [resultLeads, setResultLeads] = React.useState<Lead[]>([]);
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [liveEntry, setLiveEntry] = React.useState<LiveSearchEntry | null>(null);

  const searchStartRef = React.useRef(0);

  React.useEffect(() => {
    if (stage !== "searching") return;
    const id = setInterval(() => {
      setElapsedMs(Date.now() - searchStartRef.current);
    }, 100);
    return () => clearInterval(id);
  }, [stage]);

  async function animateProvider(index: number) {
    await delay(index * 150);
    setProviders((prev) =>
      prev.map((p, i) => (i === index ? { ...p, status: "searching" as const } : p)),
    );

    const steps = 5 + Math.floor(Math.random() * 4);
    for (let s = 1; s <= steps; s++) {
      await delay(140 + Math.random() * 160);
      const progress = Math.round((s / steps) * 100);
      setProviders((prev) => prev.map((p, i) => (i === index ? { ...p, progress } : p)));
    }

    const found = 9 + Math.floor(Math.random() * 38);
    setProviders((prev) =>
      prev.map((p, i) =>
        i === index ? { ...p, status: "done" as const, progress: 100, found } : p,
      ),
    );
    setLeadsFound((prev) => prev + found);
  }

  async function runSearch(overrideQuery?: string) {
    if (stage === "searching") return;
    const activeQuery = overrideQuery ?? query;
    if (overrideQuery !== undefined) setQuery(overrideQuery);

    searchStartRef.current = Date.now();
    setElapsedMs(0);
    setLeadsFound(0);
    setSelectedIds([]);
    setResultLeads([]);
    setLiveEntry(null);

    const initialProviders: ProviderRun[] = PROVIDER_NAMES.map((name) => ({
      id: name.toLowerCase().replace(/\s+/g, "-"),
      name,
      status: "pending" as const,
      progress: 0,
      found: 0,
    }));
    setProviders(initialProviders);
    setStage("searching");

    setLiveEntry({
      query: activeQuery || "Untitled search",
      location: filters.cities.length
        ? filters.cities.join(", ")
        : filters.country !== "all"
          ? filters.country
          : "All locations",
      status: "running",
      results: 0,
    });

    await Promise.all(PROVIDER_NAMES.map((_, i) => animateProvider(i)));

    const results = computeResults(activeQuery, filters);
    setResultLeads(results);
    setStage("results");
    setLiveEntry({
      query: activeQuery || "Untitled search",
      location: filters.cities.length
        ? filters.cities.join(", ")
        : filters.country !== "all"
          ? filters.country
          : "All locations",
      status: "completed",
      results: results.length,
    });
  }

  const overallProgress = React.useMemo(() => {
    if (providers.length === 0) return 0;
    return Math.round(providers.reduce((sum, p) => sum + p.progress, 0) / providers.length);
  }, [providers]);

  function toggleSelect(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }
  function selectAll() {
    setSelectedIds(resultLeads.map((l) => l.id));
  }
  function clearSelection() {
    setSelectedIds([]);
  }

  return (
    <div>
      <PageHeader
        title="Lead Search"
        description="Discover high-quality, AI-scored leads across Google Places, IndiaMART, JustDial and more."
      />

      <SearchBar
        query={query}
        onQueryChange={setQuery}
        onSearch={() => runSearch()}
        isSearching={stage === "searching"}
      />

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[300px_1fr]">
        <div className="space-y-6 lg:order-1 order-2">
          <FilterPanel filters={filters} onChange={setFilters} />
          <SearchTimeline history={searchHistory} live={liveEntry} />
        </div>

        <div className="lg:order-2 order-1">
          <AnimatePresence mode="wait">
            {stage === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
              >
                <SearchIdle onQuickStart={(q) => runSearch(q)} />
              </motion.div>
            )}

            {stage === "searching" && (
              <motion.div
                key="searching"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
              >
                <SearchProgress
                  providers={providers}
                  overallProgress={overallProgress}
                  elapsedMs={elapsedMs}
                  leadsFound={leadsFound}
                  query={query}
                />
              </motion.div>
            )}

            {stage === "results" && (
              <motion.div
                key="results"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
              >
                <ResultsGrid
                  leads={resultLeads}
                  selectedIds={selectedIds}
                  onToggleSelect={toggleSelect}
                  onSelectAll={selectAll}
                  onClearSelection={clearSelection}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
