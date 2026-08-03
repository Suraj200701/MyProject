"use client";

import { Gauge, Percent, Target, Users } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/shared/stat-card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/utils";
import { useDashboardStats } from "@/lib/api/queries";
import { SectionHeading } from "@/components/intelligence/section-heading";
import { TopIndustriesCard } from "@/components/intelligence/top-industries-card";
import { TopCitiesCard } from "@/components/intelligence/top-cities-card";
import { LeadTrendsChart } from "@/components/intelligence/lead-trends-chart";
import { SearchPerformanceCard } from "@/components/intelligence/search-performance-card";
import { ProviderPerformanceCard } from "@/components/intelligence/provider-performance-card";
import { LeadQualityCard } from "@/components/intelligence/lead-quality-card";
import { BusinessAnalyticsCard } from "@/components/intelligence/business-analytics-card";

/**
 * Two things were removed here, both because they showed numbers nobody measured:
 *
 * 1. **The date-range selector.** It multiplied the real lead total by a
 *    hardcoded factor per range (7d = 0.24x, 90d = 2.9x, …). None of the five
 *    analytics endpoints this page reads accepts a range parameter, so the
 *    control could not filter anything — it only scaled a number to look like it
 *    had. Restoring it means adding `from`/`to` parameters to the analytics
 *    endpoints first; until then a control that silently fabricates its output is
 *    worse than no control.
 *
 * 2. **The trend deltas** ("+12.4%", "+3.1 pts"). The backend exposes no
 *    previous-period figures, so these were invented. `change` is optional on
 *    StatCard, so the tiles render without them.
 */
export default function IntelligencePage() {
  const { data: stats, isPending } = useDashboardStats();

  // Leads per search — a real ratio over two real figures.
  const searchToLeadRatio = stats
    ? (stats.totalLeads / Math.max(1, stats.searchCount)).toFixed(1)
    : "—";

  return (
    <div>
      <PageHeader
        title="Lead Intelligence"
        description="Understand lead quality, search performance, and where your best leads come from."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {isPending || !stats ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[116px] rounded-xl" />)
        ) : (
          <>
            <StatCard
              label="Total Leads"
              value={formatNumber(stats.totalLeads)}
              icon={Users}
              accent="primary"
            />
            <StatCard
              label="Avg Lead Score"
              value={String(stats.avgLeadScore)}
              icon={Gauge}
              accent="accent"
            />
            <StatCard
              label="Conversion Rate"
              value={`${stats.conversionRate}%`}
              icon={Target}
              accent="success"
            />
            <StatCard
              label="Search-to-Lead Ratio"
              value={`1 : ${searchToLeadRatio}`}
              icon={Percent}
              accent="warning"
            />
          </>
        )}
      </div>

      <div className="mt-8">
        <SectionHeading title="Lead Trends" />
        <LeadTrendsChart />
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <SectionHeading title="Top Industries" />
          <TopIndustriesCard />
        </div>
        <div>
          <SectionHeading title="Top Cities" />
          <TopCitiesCard />
        </div>
      </div>

      <div className="mt-8">
        <SectionHeading title="Search Performance" />
        <SearchPerformanceCard />
      </div>

      <div className="mt-8">
        <SectionHeading title="Provider Performance" />
        <ProviderPerformanceCard />
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <SectionHeading title="Lead Quality" />
          <LeadQualityCard />
        </div>
        <div>
          <SectionHeading title="Business Analytics" />
          <BusinessAnalyticsCard />
        </div>
      </div>
    </div>
  );
}
