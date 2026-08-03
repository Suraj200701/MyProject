"use client";

import { Database, Gauge, Search, Target, UserPlus, Wallet } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/shared/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/utils";
import { useDashboardStats } from "@/lib/api/queries";
import { LeadGrowthChart } from "@/components/dashboard/lead-growth-chart";
import { IndustryDistributionChart } from "@/components/dashboard/industry-distribution-chart";
import { SearchAnalyticsChart } from "@/components/dashboard/search-analytics-chart";
import { ApiUsageChart } from "@/components/dashboard/api-usage-chart";
import { CountryAnalyticsChart } from "@/components/dashboard/country-analytics-chart";
import { ExportAnalyticsChart } from "@/components/dashboard/export-analytics-chart";
import { AiRecommendations } from "@/components/dashboard/ai-recommendations";
import { RecentSearches } from "@/components/dashboard/recent-searches";
import { HighValueLeads } from "@/components/dashboard/high-value-leads";
import { WebsiteScanResults } from "@/components/dashboard/website-scan-results";
import { ProviderHealth } from "@/components/dashboard/provider-health";
import { DailyReport } from "@/components/dashboard/daily-report";

/**
 * The six headline tiles.
 *
 * The previous version carried period-over-period deltas ("+12.4%"), but the
 * backend exposes no comparison window — those figures were invented. `change`
 * is optional on StatCard, so the tiles simply render without a delta rather
 * than showing a trend nobody measured. Adding one back means adding a
 * previous-period figure to `GET /dashboard/stats` first.
 */
function useStatTiles() {
  const { data: stats, isPending, isError, error, refetch } = useDashboardStats();

  const tiles = stats
    ? ([
        {
          label: "Total Leads",
          value: formatNumber(stats.totalLeads),
          icon: Database,
          accent: "primary" as const,
        },
        {
          label: "Today's Leads",
          value: formatNumber(stats.todayLeads),
          icon: UserPlus,
          accent: "accent" as const,
        },
        {
          label: "Conversion Rate",
          value: `${stats.conversionRate}%`,
          icon: Target,
          accent: "success" as const,
        },
        {
          label: "Avg Lead Score",
          value: `${stats.avgLeadScore}`,
          icon: Gauge,
          accent: "warning" as const,
        },
        {
          label: "Search Count",
          value: formatNumber(stats.searchCount),
          icon: Search,
          accent: "primary" as const,
        },
        {
          label: "Credits Remaining",
          value: `${formatNumber(stats.creditsRemaining)} / ${formatNumber(stats.creditsTotal)}`,
          icon: Wallet,
          accent: "accent" as const,
        },
      ])
    : [];

  return { tiles, isPending, isError, error, refetch };
}

export default function DashboardPage() {
  const { tiles, isPending, isError } = useStatTiles();

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Dashboard" description="Welcome back — here's what's happening with your leads." />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {isPending
          ? // Six skeletons at the tile's own height, so the grid doesn't jump
            // when the real numbers arrive.
            Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-[116px] rounded-xl" />
            ))
          : isError
            ? (
                <div className="col-span-full rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
                  Couldn&apos;t load your dashboard stats. Check that the backend is running.
                </div>
              )
            : tiles.map((stat, i) => (
                <div
                  key={stat.label}
                  className="animate-fade-up"
                  style={{ animationDelay: `${i * 60}ms`, animationFillMode: "backwards" }}
                >
                  <StatCard
                    label={stat.label}
                    value={stat.value}
                    icon={stat.icon}
                    accent={stat.accent}
                  />
                </div>
              ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="animate-fade-up lg:col-span-2" style={{ animationDelay: "80ms", animationFillMode: "backwards" }}>
          <LeadGrowthChart />
        </div>
        <div className="animate-fade-up" style={{ animationDelay: "140ms", animationFillMode: "backwards" }}>
          <IndustryDistributionChart />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="animate-fade-up" style={{ animationDelay: "80ms", animationFillMode: "backwards" }}>
          <SearchAnalyticsChart />
        </div>
        <div className="animate-fade-up" style={{ animationDelay: "140ms", animationFillMode: "backwards" }}>
          <ApiUsageChart />
        </div>
        <div className="animate-fade-up" style={{ animationDelay: "200ms", animationFillMode: "backwards" }}>
          <CountryAnalyticsChart />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="animate-fade-up lg:col-span-2" style={{ animationDelay: "80ms", animationFillMode: "backwards" }}>
          <ExportAnalyticsChart />
        </div>
        <div className="animate-fade-up" style={{ animationDelay: "140ms", animationFillMode: "backwards" }}>
          <DailyReport />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="animate-fade-up" style={{ animationDelay: "80ms", animationFillMode: "backwards" }}>
          <AiRecommendations />
        </div>
        <div className="animate-fade-up" style={{ animationDelay: "140ms", animationFillMode: "backwards" }}>
          <RecentSearches />
        </div>
        <div className="animate-fade-up" style={{ animationDelay: "200ms", animationFillMode: "backwards" }}>
          <HighValueLeads />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="animate-fade-up" style={{ animationDelay: "80ms", animationFillMode: "backwards" }}>
          <WebsiteScanResults />
        </div>
        <div className="animate-fade-up" style={{ animationDelay: "140ms", animationFillMode: "backwards" }}>
          <ProviderHealth />
        </div>
      </div>
    </div>
  );
}
