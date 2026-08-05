"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/page-header";
import { SearchBar } from "@/components/search/search-bar";
import { LeadSourceSelector, type LeadSource } from "@/components/search/lead-source-selector";
import { MapMode } from "@/components/search/map-mode";
import { FilterPanel } from "@/components/search/filter-panel";
import { SearchIdle } from "@/components/search/search-idle";
import { SearchProgress } from "@/components/search/search-progress";
import { ResultsGrid } from "@/components/search/results-grid";
import { SearchTimeline, type LiveSearchEntry } from "@/components/search/search-timeline";
import {
  defaultFilters,
  type ProviderRun,
  type SearchFilters,
  type SearchStage,
} from "@/components/search/types";
import { ApiError, errorMessage } from "@/lib/api/client";
import { leadsApi } from "@/lib/api/endpoints";
import { toLeads } from "@/lib/api/mappers";
import { useProviders, useRunSearch, useSearchHistory } from "@/lib/api/queries";
import type { Lead } from "@/lib/types";

/**
 * Lead Search, backed by `POST /search`.
 *
 * What changed, and why it matters
 * --------------------------------
 * The previous implementation faked the entire search. It animated four
 * hardcoded provider names with `Math.random()` progress bars and invented a
 * "found" count per provider, then filtered a fixture — and if nothing matched,
 * it **shuffled the fixture and returned a random slice** so the grid never
 * looked empty. All of that is gone.
 *
 * `POST /search` is a single synchronous call: it queries every configured
 * provider concurrently server-side and returns real per-provider runs
 * (`provider_runs[]`, each with a status and a real `results_found`). So the
 * progress panel now shows providers as pending while the request is in flight,
 * then their true outcomes when it resolves. There is no per-provider streaming
 * to subscribe to, so the bars complete together rather than pretending to
 * advance independently.
 *
 * Fetching the results: the search response carries counts, not the lead rows,
 * and `GET /leads` has no `search_id` filter. Since a search creates its leads
 * immediately before responding, the newest `results_count` leads *are* that
 * search's results, so they are fetched newest-first. That is an approximation
 * only if another member creates leads in the same instant; adding `search_id`
 * to the leads endpoint would make it exact.
 *
 * Client-side filters: the search endpoint accepts `query`, `location`,
 * `industry` and `country`. The panel's other controls (provider, company type,
 * min rating, score range, keywords) have no equivalent, so they are applied to
 * the returned results rather than silently ignored.
 */
export default function SearchPage() {
  const [query, setQuery] = React.useState("");
  /**
   * Which sources to search.
   *
   * Defaults to Auto: it tries the providers you have configured and falls back
   * to public map data, so the page returns something useful on a deployment
   * with no API keys yet instead of an empty result and a row of skipped
   * providers.
   */
  const [source, setSource] = React.useState<LeadSource>("auto");
  const [filters, setFilters] = React.useState<SearchFilters>(defaultFilters);
  const [stage, setStage] = React.useState<SearchStage>("idle");
  const [providerRuns, setProviderRuns] = React.useState<ProviderRun[]>([]);
  const [leadsFound, setLeadsFound] = React.useState(0);
  const [elapsedMs, setElapsedMs] = React.useState(0);
  const [resultLeads, setResultLeads] = React.useState<Lead[]>([]);
  const [selectedIds, setSelectedIds] = React.useState<string[]>([]);
  const [liveEntry, setLiveEntry] = React.useState<LiveSearchEntry | null>(null);

  const searchStartRef = React.useRef(0);

  const { data: providerCatalogue } = useProviders();
  const { data: history } = useSearchHistory({ page_size: 5 });
  const runSearch = useRunSearch();

  React.useEffect(() => {
    if (stage !== "searching") return;
    const id = setInterval(() => setElapsedMs(Date.now() - searchStartRef.current), 100);
    return () => clearInterval(id);
  }, [stage]);

  /** Where the search is scoped to, for the timeline label. */
  const locationLabel = React.useCallback(() => {
    if (filters.cities.length) return filters.cities.join(", ");
    if (filters.country !== "all") return filters.country;
    return "All locations";
  }, [filters.cities, filters.country]);

  /** Applies the filters the search endpoint can't express. */
  const applyClientFilters = React.useCallback(
    (leads: Lead[]): Lead[] =>
      leads.filter((lead) => {
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
        return true;
      }),
    [filters],
  );

  async function startSearch(overrideQuery?: string) {
    if (stage === "searching") return;
    const activeQuery = (overrideQuery ?? query).trim();
    if (overrideQuery !== undefined) setQuery(overrideQuery);

    if (!activeQuery) {
      toast.error("Enter what you're looking for to run a search.");
      return;
    }

    searchStartRef.current = Date.now();
    setElapsedMs(0);
    setLeadsFound(0);
    setSelectedIds([]);
    setResultLeads([]);

    // Seed the panel from the real provider catalogue rather than four
    // hardcoded names, so it lists the providers that will actually be queried.
    setProviderRuns(
      (providerCatalogue ?? []).map((p) => ({
        id: p.id,
        name: p.name,
        status: "pending" as const,
        progress: 0,
        found: 0,
      })),
    );
    setStage("searching");
    setLiveEntry({ query: activeQuery, location: locationLabel(), status: "running", results: 0 });

    try {
      const search = await runSearch.mutateAsync({
        query: activeQuery,
        mode: source,
        location: filters.cities.length ? filters.cities.join(", ") : undefined,
        industry: filters.industry !== "all" ? filters.industry : undefined,
        country: filters.country !== "all" ? filters.country : undefined,
      });

      // Real per-provider outcomes from the response.
      setProviderRuns(
        search.provider_runs.map((run) => ({
          id: run.provider_id,
          name: run.provider_name,
          status: "done" as const,
          progress: 100,
          found: run.results_found,
        })),
      );
      setLeadsFound(search.results_count);

      // The leads this search just created are the newest ones.
      let leads: Lead[] = [];
      if (search.results_count > 0) {
        const page = await leadsApi.list({
          page_size: Math.min(100, Math.max(1, search.results_count)),
          sort_by: "created_at",
          sort_order: "desc",
        });
        leads = applyClientFilters(toLeads(page.items));
      }

      setResultLeads(leads);
      setStage("results");
      setLiveEntry({
        query: activeQuery,
        location: locationLabel(),
        status: "completed",
        results: search.results_count,
      });

      if (search.results_count === 0) {
        // Truthful empty result. The provider panel above shows which providers
        // were skipped and why, which is the actionable part.
        toast.info("That search returned no leads.", {
          description: "No configured provider returned a match — check the provider panel.",
        });
      }
    } catch (error) {
      setStage("idle");
      setProviderRuns([]);
      setLiveEntry(null);
      if (error instanceof ApiError && error.isPaymentRequired) {
        toast.error(error.message, { description: "Top up your credits to run more searches." });
      } else {
        toast.error(errorMessage(error));
      }
    }
  }

  const overallProgress = React.useMemo(() => {
    if (providerRuns.length === 0) return 0;
    return Math.round(providerRuns.reduce((sum, p) => sum + p.progress, 0) / providerRuns.length);
  }, [providerRuns]);

  function toggleSelect(id: string) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  return (
    <div>
      <PageHeader
        title="Lead Search"
        description="Discover high-quality, AI-scored leads across every provider you've connected."
      />

      <div className="mb-5">
        <LeadSourceSelector
          value={source}
          onChange={setSource}
          disabled={stage === "searching"}
        />
      </div>

      {/* Map Mode is a review workflow — extract, look, pick, import — so it
          replaces the one-shot search bar rather than sitting alongside it. */}
      {source === "map" ? (
        <MapMode />
      ) : (
        <>
          <SearchBar
            query={query}
            onQueryChange={setQuery}
            onSearch={() => startSearch()}
            isSearching={stage === "searching"}
          />

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[300px_1fr]">
        <div className="space-y-6 lg:order-1 order-2">
          <FilterPanel filters={filters} onChange={setFilters} />
          <SearchTimeline history={history?.items ?? []} live={liveEntry} />
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
                <SearchIdle onQuickStart={(q) => startSearch(q)} />
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
                  providers={providerRuns}
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
                  onSelectAll={() => setSelectedIds(resultLeads.map((l) => l.id))}
                  onClearSelection={() => setSelectedIds([])}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
          </div>
        </>
      )}
    </div>
  );
}
