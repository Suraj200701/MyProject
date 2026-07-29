"use client";

import * as React from "react";
import { PageHeader } from "@/components/shared/page-header";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiProviders } from "@/lib/mock-data";
import { StatsRow } from "@/components/api-manager/stats-row";
import { AddProviderDialog } from "@/components/api-manager/add-provider-dialog";
import { ProviderCard } from "@/components/api-manager/provider-card";
import { HealthStatus } from "@/components/api-manager/health-status";
import { UsageAnalytics } from "@/components/api-manager/usage-analytics";
import { CATEGORY_TABS, categoryTabLabel, type CategoryTab } from "@/components/api-manager/mock-extras";

export default function ApiManagerPage() {
  const [tab, setTab] = React.useState<CategoryTab>("All");

  const filtered = tab === "All" ? apiProviders : apiProviders.filter((p) => p.category === tab);

  return (
    <div>
      <PageHeader
        title="API Manager"
        description="Connect, monitor, and test the data providers powering your lead search."
        actions={<AddProviderDialog />}
      />

      <StatsRow providers={apiProviders} />

      <Tabs value={tab} onValueChange={(v) => setTab(v as CategoryTab)} className="mt-6">
        <TabsList>
          {CATEGORY_TABS.map((t) => (
            <TabsTrigger key={t} value={t}>
              {categoryTabLabel(t)}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {filtered.map((provider) => (
          <ProviderCard key={provider.id} provider={provider} />
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <HealthStatus providers={apiProviders} />
        <UsageAnalytics providers={apiProviders} />
      </div>
    </div>
  );
}
