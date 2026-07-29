"use client";

import * as React from "react";
import { toast } from "sonner";
import { Settings2 } from "lucide-react";
import type { ApiProvider } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { StatusPill } from "@/components/api-manager/status-pill";
import { ProviderDetailDialog } from "@/components/api-manager/provider-detail-dialog";

export function ProviderCard({ provider }: { provider: ApiProvider }) {
  const [open, setOpen] = React.useState(false);
  const [connected, setConnected] = React.useState(provider.connected);
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
          <div className="flex items-center gap-2">
            <Switch
              checked={connected}
              onCheckedChange={(v) => {
                setConnected(v);
                toast.success(v ? `${provider.name} connected` : `${provider.name} disconnected`);
              }}
            />
            <span className="text-xs text-muted-foreground">{connected ? "Connected" : "Disconnected"}</span>
          </div>
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
