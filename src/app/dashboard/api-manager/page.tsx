"use client";

import * as React from "react";
import { AlertCircle, Plug } from "lucide-react";

import { PageHeader } from "@/components/shared/page-header";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { StatsRow } from "@/components/api-manager/stats-row";
import { AddProviderDialog } from "@/components/api-manager/add-provider-dialog";
import { ProviderCard } from "@/components/api-manager/provider-card";
import { HealthStatus } from "@/components/api-manager/health-status";
import { UsageAnalytics } from "@/components/api-manager/usage-analytics";
import {
  CATEGORY_TABS,
  categoryTabLabel,
  type CategoryTab,
} from "@/components/api-manager/provider-utils";
import { errorMessage } from "@/lib/api/client";
import { useProviders } from "@/lib/api/queries";

export default function ApiManagerPage() {
  const [tab, setTab] = React.useState<CategoryTab>("All");
  // The real seeded catalogue from GET /providers, with real usage, latency and
  // health — not the eight-item fixture, which listed providers such as
  // Hunter.io that the backend has no adapter for.
  const { data: providers, isPending, isError, error } = useProviders();

  const all = providers ?? [];
  const filtered = tab === "All" ? all : all.filter((p) => p.category === tab);

  return (
    <div>
      <PageHeader
        title="API Manager"
        description="Connect, monitor, and test the data providers powering your lead search."
        actions={<AddProviderDialog />}
      />

      {isPending ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[100px] rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <EmptyState
          icon={AlertCircle}
          title="Couldn't load providers"
          description={errorMessage(error)}
        />
      ) : (
        <>
          <StatsRow providers={all} />

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
            {filtered.length === 0 ? (
              <div className="sm:col-span-2 xl:col-span-3">
                <EmptyState
                  icon={Plug}
                  title={`No ${tab === "All" ? "" : `${tab} `}providers`}
                  description="Nothing in this category is configured yet."
                />
              </div>
            ) : (
              filtered.map((provider) => <ProviderCard key={provider.id} provider={provider} />)
            )}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <HealthStatus providers={all} />
            <UsageAnalytics providers={all} />
          </div>
        </>
      )}
    </div>
  );
}
