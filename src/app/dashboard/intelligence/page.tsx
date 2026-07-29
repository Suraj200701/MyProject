"use client";

import * as React from "react";
import { Gauge, Percent, Target, Users } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/shared/stat-card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { dashboardStats } from "@/lib/mock-data";
import { formatNumber } from "@/lib/utils";
import { SectionHeading } from "@/components/intelligence/section-heading";
import { TopIndustriesCard } from "@/components/intelligence/top-industries-card";
import { TopCitiesCard } from "@/components/intelligence/top-cities-card";
import { LeadTrendsChart } from "@/components/intelligence/lead-trends-chart";
import { SearchPerformanceCard } from "@/components/intelligence/search-performance-card";
import { ProviderPerformanceCard } from "@/components/intelligence/provider-performance-card";
import { LeadQualityCard } from "@/components/intelligence/lead-quality-card";
import { BusinessAnalyticsCard } from "@/components/intelligence/business-analytics-card";

const RANGE_MULTIPLIER: Record<string, number> = {
  "7d": 0.24,
  "30d": 1,
  "90d": 2.9,
  all: 4.1,
};

export default function IntelligencePage() {
  const [range, setRange] = React.useState("30d");
  const multiplier = RANGE_MULTIPLIER[range];

  const searchToLeadRatio = (dashboardStats.totalLeads / Math.max(1, dashboardStats.searchCount)).toFixed(1);

  return (
    <div>
      <PageHeader
        title="Lead Intelligence"
        description="Understand lead quality, search performance, and where your best leads come from."
        actions={
          <Select value={range} onValueChange={setRange}>
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
              <SelectItem value="all">All time</SelectItem>
            </SelectContent>
          </Select>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total Leads"
          value={formatNumber(Math.round(dashboardStats.totalLeads * multiplier))}
          icon={Users}
          accent="primary"
          change={{ value: "+12.4%", positive: true }}
        />
        <StatCard
          label="Avg Lead Score"
          value={String(dashboardStats.avgLeadScore)}
          icon={Gauge}
          accent="accent"
          change={{ value: "+3.1 pts", positive: true }}
        />
        <StatCard
          label="Conversion Rate"
          value={`${dashboardStats.conversionRate}%`}
          icon={Target}
          accent="success"
          change={{ value: "+2.1%", positive: true }}
        />
        <StatCard
          label="Search-to-Lead Ratio"
          value={`1 : ${searchToLeadRatio}`}
          icon={Percent}
          accent="warning"
          change={{ value: "+0.4", positive: true }}
        />
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
