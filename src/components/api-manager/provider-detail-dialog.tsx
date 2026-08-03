"use client";

import { Info } from "lucide-react";
import type { ApiProvider } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusPill } from "@/components/api-manager/status-pill";
import {
  isNearQuota,
  latencyLabel,
  remainingQuota,
  usagePercent,
} from "@/components/api-manager/provider-utils";

/**
 * Provider detail.
 *
 * Three tabs were rebuilt because all three showed fabricated data:
 *
 *   * **Playground** — "Test Connection" waited 900ms and rendered a
 *     category-flavoured JSON blob with a hardcoded `200 OK` and made-up
 *     latency. No provider ever received a request. There is no
 *     test-connection endpoint, so the tab now explains how to verify a
 *     provider for real (run a search and read its provider runs).
 *   * **Credentials** — displayed a plausible `sk_live_…` key and a
 *     "Regenerate key" button that only re-seeded the fake string. Provider
 *     credentials are stored encrypted server-side and are deliberately never
 *     returned by any endpoint, so the tab now says where keys are actually set.
 *   * **Usage** — a 7-day sparkline built from a PRNG. `ApiProvider` holds one
 *     cumulative `usage_count`, not a time series, so the tab shows real
 *     cumulative usage against the real quota instead of an invented history.
 */
export function ProviderDetailDialog({
  provider,
  open,
  onOpenChange,
}: {
  provider: ApiProvider;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const percent = usagePercent(provider);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="text-lg">{provider.logo}</span>
            {provider.name}
            <StatusPill status={provider.status} className="ml-1" />
          </DialogTitle>
          <DialogDescription>{provider.description}</DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="usage">
          <TabsList>
            <TabsTrigger value="usage">Usage</TabsTrigger>
            <TabsTrigger value="credentials">Credentials</TabsTrigger>
            <TabsTrigger value="testing">Testing</TabsTrigger>
          </TabsList>

          <TabsContent value="usage">
            <div className="flex items-baseline justify-between">
              <p className="text-sm font-medium">
                {provider.usage.toLocaleString()}
                <span className="text-muted-foreground">
                  {" / "}
                  {provider.limit > 0 ? provider.limit.toLocaleString() : "unlimited"}
                </span>
              </p>
              {provider.limit > 0 ? (
                <span className="text-xs tabular-nums text-muted-foreground">{percent}%</span>
              ) : null}
            </div>
            {provider.limit > 0 ? <Progress value={percent} className="mt-2" /> : null}
            <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div>
                <dt className="text-muted-foreground">Remaining</dt>
                <dd className="mt-0.5 font-medium text-foreground">
                  {provider.limit > 0 ? remainingQuota(provider).toLocaleString() : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Latency</dt>
                <dd className="mt-0.5 font-medium text-foreground">{latencyLabel(provider)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Connected</dt>
                <dd className="mt-0.5 font-medium text-foreground">
                  {provider.connected ? "Yes" : "No"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Category</dt>
                <dd className="mt-0.5 font-medium text-foreground">{provider.category}</dd>
              </div>
            </dl>
            {isNearQuota(provider) ? (
              <p className="mt-3 text-xs text-warning">
                This provider is at {percent}% of its quota.
              </p>
            ) : null}
            <p className="mt-3 flex items-start gap-1.5 text-[11px] text-muted-foreground">
              <Info className="mt-0.5 size-3 shrink-0" />
              Usage is cumulative. Per-day history isn&apos;t recorded, so there&apos;s no trend to
              chart here.
            </p>
          </TabsContent>

          <TabsContent value="credentials">
            <p className="text-xs text-muted-foreground">
              Provider credentials are stored encrypted on the server and are never sent back to
              the browser — not even masked.
            </p>
            <p className="mt-3 text-xs text-muted-foreground">
              Set them as environment variables on the backend (for example{" "}
              <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[11px]">
                GOOGLE_MAPS_API_KEY
              </code>
              ,{" "}
              <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[11px]">
                MAPPLS_CLIENT_ID
              </code>
              ), then restart the API. A provider with no credentials is skipped during a search
              rather than charged for.
            </p>
          </TabsContent>

          <TabsContent value="testing">
            <p className="text-xs text-muted-foreground">
              There&apos;s no isolated test-connection endpoint. To verify this provider end to end,
              run a search from Lead Search — the results panel lists every provider that was
              queried, whether it succeeded, and how many leads it returned.
            </p>
            <p className="mt-3 text-xs text-muted-foreground">
              A provider that is missing credentials is reported as skipped, with the reason, rather
              than failing the search.
            </p>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
