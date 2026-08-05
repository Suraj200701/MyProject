"use client";

import * as React from "react";
import { Settings2 } from "lucide-react";
import type { ApiProvider } from "@/lib/types";
import type { ProviderCredentialStatusOut } from "@/lib/api/types";
import { useProviderCredentials } from "@/lib/api/queries";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { StatusPill } from "@/components/api-manager/status-pill";
import { ProviderDetailDialog } from "@/components/api-manager/provider-detail-dialog";

/**
 * Whether this provider can actually run, and why.
 *
 * Derived from the credential status the backend reports, not from
 * `provider.connected`. That column records "this workspace saved its own
 * credentials" — so a provider configured through `.env`, or one that needs no
 * credential at all, read "Disconnected" while working perfectly. Every
 * provider on the page showed Disconnected, including OpenStreetMap, which
 * cannot have a credential.
 */
function describeCredential(status: ProviderCredentialStatusOut | undefined) {
  switch (status?.source) {
    case "none_required":
      return { ready: true, label: "No key required", hint: "This provider is free to use and needs no credential." };
    case "workspace":
      return { ready: true, label: "Connected", hint: "Using the key saved for this workspace." };
    case "environment":
      return { ready: true, label: "Connected", hint: "Using the key from the backend's .env." };
    case "unset":
      return { ready: false, label: "Not configured", hint: "Add a key under Manage → Credentials to enable it." };
    default:
      // Status not loaded yet — say nothing rather than guess.
      return { ready: false, label: "Checking…", hint: "Loading credential status." };
  }
}

export function ProviderCard({ provider }: { provider: ApiProvider }) {
  const [open, setOpen] = React.useState(false);
  const { data: credentials } = useProviderCredentials();
  const credential = describeCredential(
    credentials?.find((c) => c.provider_id === provider.id),
  );
  const usagePct = provider.limit ? Math.round((provider.usage / provider.limit) * 100) : 0;

  return (
    <>
      <Card className="flex flex-col p-5 transition-colors hover:border-border-strong">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl border border-border bg-surface-2 text-lg">
              {provider.logo}
            </div>
            <div>
              <p className="text-sm font-semibold">{provider.name}</p>
              <Badge variant="outline" className="mt-0.5">
                {provider.category}
              </Badge>
            </div>
          </div>
          <StatusPill status={provider.status} />
        </div>

        <p className="mt-3 text-xs text-muted-foreground">{provider.description}</p>

        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Usage</span>
            <span className="tabular-nums">
              {provider.usage.toLocaleString()} / {provider.limit.toLocaleString()}
            </span>
          </div>
          <Progress value={usagePct} className="mt-1.5" />
        </div>

        <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 text-xs",
              credential.ready ? "text-success" : "text-muted-foreground",
            )}
            title={credential.hint}
          >
            <span
              aria-hidden
              className={cn(
                "size-1.5 rounded-full",
                credential.ready ? "bg-success" : "bg-muted-foreground/50",
              )}
            />
            {credential.label}
          </span>
          <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
            <Settings2 className="size-3.5" />
            Manage
          </Button>
        </div>
      </Card>

      <ProviderDetailDialog provider={provider} open={open} onOpenChange={setOpen} />
    </>
  );
}
