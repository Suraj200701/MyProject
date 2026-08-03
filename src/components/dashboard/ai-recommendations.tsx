"use client";

/**
 * Suggested next actions.
 *
 * The previous version listed four hardcoded sentences ("12 high-score leads
 * match your Electrical Dealers ICP…") that referenced numbers and providers
 * that did not exist. There is no recommendations endpoint on the backend, so
 * rather than keep inventing copy, each row here is **derived from data the
 * dashboard has already fetched** and is only shown when its condition actually
 * holds:
 *
 *   * a provider is degraded or down          -> from GET /providers
 *   * credits are nearly exhausted            -> from GET /dashboard/stats
 *   * there are no leads yet                  -> from GET /dashboard/stats
 *   * high-scoring leads are waiting          -> from GET /leads (score >= 80)
 *   * leads are missing contact details       -> from GET /leads
 *
 * Every line is therefore a true statement about this workspace. If a real
 * recommendations endpoint is added later, this component swaps to it without
 * the surrounding layout changing.
 */

import * as React from "react";
import { ArrowUpRight, Sparkles } from "lucide-react";
import Link from "next/link";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { AsyncContent, SkeletonRows } from "@/components/shared/async-content";
import { useDashboardStats, useLeads, useProviders } from "@/lib/api/queries";

interface Recommendation {
  text: string;
  href: string;
}

export function AiRecommendations() {
  const { data: stats, isPending: statsPending, isError, error } = useDashboardStats();
  const { data: providers } = useProviders();
  // A small sample is enough to spot "leads are missing emails" without pulling
  // the whole database into the browser.
  const { data: leadSample } = useLeads({ page_size: 50, sort_by: "lead_score", sort_order: "desc" });

  const recommendations = React.useMemo<Recommendation[]>(() => {
    const out: Recommendation[] = [];
    const leads = leadSample?.items ?? [];

    const unhealthy = (providers ?? []).filter((p) => p.status !== "healthy");
    if (unhealthy.length > 0) {
      const names = unhealthy.slice(0, 2).map((p) => p.name).join(" and ");
      out.push({
        text: `${names} ${unhealthy.length === 1 ? "is" : "are"} not healthy — check the provider status before your next search`,
        href: "/dashboard/api-manager",
      });
    }

    if (stats && stats.creditsTotal > 0) {
      const remainingPct = (stats.creditsRemaining / stats.creditsTotal) * 100;
      if (remainingPct <= 20) {
        out.push({
          text: `Only ${stats.creditsRemaining.toLocaleString()} credits left (${Math.round(remainingPct)}% of your plan) — top up before your next search`,
          href: "/dashboard/billing",
        });
      }
    }

    if (stats && stats.totalLeads === 0) {
      out.push({
        text: "You have no leads yet — run your first search to start building the database",
        href: "/dashboard/search",
      });
    }

    const highScoring = leads.filter((l) => l.leadScore >= 80).length;
    if (highScoring > 0) {
      out.push({
        text: `${highScoring} lead${highScoring === 1 ? "" : "s"} scored 80 or above — review the highest-intent ones first`,
        href: "/dashboard/leads",
      });
    }

    const missingContact = leads.filter((l) => !l.email && !l.phone).length;
    if (missingContact > 0) {
      out.push({
        text: `${missingContact} lead${missingContact === 1 ? " has" : "s have"} no email or phone — the Website Scanner can fill those in`,
        href: "/dashboard/scanner",
      });
    }

    if (stats && stats.searchCount === 0 && stats.totalLeads > 0) {
      out.push({
        text: "Your leads were imported rather than searched — try a search to discover new companies",
        href: "/dashboard/search",
      });
    }

    return out.slice(0, 4);
  }, [stats, providers, leadSample]);

  return (
    <Card className="glass overflow-hidden">
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <div className="flex size-7 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <Sparkles className="size-3.5" />
        </div>
        <CardTitle>AI Recommendations</CardTitle>
      </CardHeader>
      <AsyncContent
        isPending={statsPending}
        isError={isError}
        error={error}
        isEmpty={recommendations.length === 0}
        emptyMessage="Nothing needs your attention right now."
        className="min-h-[180px] p-5"
        skeleton={<SkeletonRows rows={4} />}
      >
        <div className="flex flex-col divide-y divide-border p-5 pt-3">
          {recommendations.map((rec) => (
            <Link
              key={rec.text}
              href={rec.href}
              className="group flex items-start gap-2 py-3 text-sm text-foreground/90 first:pt-0 last:pb-0 hover:text-foreground"
            >
              <span className="flex-1">{rec.text}</span>
              <ArrowUpRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-primary" />
            </Link>
          ))}
        </div>
      </AsyncContent>
    </Card>
  );
}
