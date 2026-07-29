import { Database, Gauge, Search, Target, UserPlus, Wallet } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/shared/stat-card";
import { dashboardStats } from "@/lib/mock-data";
import { formatNumber } from "@/lib/utils";
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

const stats: {
  label: string;
  value: string;
  change: { value: string; positive: boolean };
  icon: typeof Database;
  accent: "primary" | "accent" | "success" | "warning";
}[] = [
  {
    label: "Total Leads",
    value: formatNumber(dashboardStats.totalLeads),
    change: { value: "+12.4%", positive: true },
    icon: Database,
    accent: "primary",
  },
  {
    label: "Today's Leads",
    value: formatNumber(dashboardStats.todayLeads),
    change: { value: "+8.2%", positive: true },
    icon: UserPlus,
    accent: "accent",
  },
  {
    label: "Conversion Rate",
    value: `${dashboardStats.conversionRate}%`,
    change: { value: "+2.1%", positive: true },
    icon: Target,
    accent: "success",
  },
  {
    label: "Avg Lead Score",
    value: `${dashboardStats.avgLeadScore}`,
    change: { value: "-1.3%", positive: false },
    icon: Gauge,
    accent: "warning",
  },
  {
    label: "Search Count",
    value: formatNumber(dashboardStats.searchCount),
    change: { value: "+15.7%", positive: true },
    icon: Search,
    accent: "primary",
  },
  {
    label: "Credits Remaining",
    value: `${formatNumber(dashboardStats.creditsRemaining)} / ${formatNumber(dashboardStats.creditsTotal)}`,
    change: { value: "68% left", positive: true },
    icon: Wallet,
    accent: "accent",
  },
];

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Dashboard" description="Welcome back — here's what's happening with your leads." />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((stat, i) => (
          <div
            key={stat.label}
            className="animate-fade-up"
            style={{ animationDelay: `${i * 60}ms`, animationFillMode: "backwards" }}
          >
            <StatCard label={stat.label} value={stat.value} change={stat.change} icon={stat.icon} accent={stat.accent} />
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
