"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AsyncContent } from "@/components/shared/async-content";
import { useProviders } from "@/lib/api/queries";

const DOT_CLASS = {
  healthy: "bg-success",
  degraded: "bg-warning",
  down: "bg-danger",
} as const;

export function ProvidersSection() {
  const { data, isPending, isError, error } = useProviders();
  const providers = data ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Providers</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          Manage connections, credentials, and health in the full API Manager.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <AsyncContent
          isPending={isPending}
          isError={isError}
          error={error}
          isEmpty={providers.length === 0}
          emptyMessage="No providers configured yet."
          className="min-h-[40px]"
        >
          <div className="flex flex-wrap gap-2">
            {providers.map((provider) => (
              <span
                key={provider.id}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2/60 px-2.5 py-1 text-xs"
              >
                {provider.logo} {provider.name}
                <span
                  className={`size-1.5 rounded-full ${DOT_CLASS[provider.status] ?? "bg-muted"}`}
                  title={provider.status}
                />
              </span>
            ))}
          </div>
        </AsyncContent>
        <Button asChild size="sm" variant="secondary">
          <Link href="/dashboard/api-manager">Manage in API Manager</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
