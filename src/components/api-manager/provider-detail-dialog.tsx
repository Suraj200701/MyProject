"use client";

import * as React from "react";
import { toast } from "sonner";
import { Copy, Loader2, PlayCircle, RefreshCcw } from "lucide-react";
import type { ApiProvider } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusPill } from "@/components/api-manager/status-pill";
import { Sparkline } from "@/components/api-manager/sparkline";
import { getMaskedApiKey, getMockResponse, getSparklineData, type MockApiResponse } from "@/components/api-manager/mock-extras";

export function ProviderDetailDialog({
  provider,
  open,
  onOpenChange,
}: {
  provider: ApiProvider;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const [keyVersion, setKeyVersion] = React.useState(0);
  const [testing, setTesting] = React.useState(false);
  const [response, setResponse] = React.useState<MockApiResponse | null>(null);

  const sparkline = React.useMemo(() => getSparklineData(provider), [provider]);
  const maskedKey = getMaskedApiKey(provider.id, keyVersion);

  function regenerate() {
    setKeyVersion((v) => v + 1);
    toast.success("API key regenerated");
  }

  function testConnection() {
    setTesting(true);
    setResponse(null);
    window.setTimeout(() => {
      setResponse(getMockResponse(provider));
      setTesting(false);
    }, 900);
  }

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

        <Tabs defaultValue="playground">
          <TabsList>
            <TabsTrigger value="playground">Playground</TabsTrigger>
            <TabsTrigger value="credentials">Credentials</TabsTrigger>
            <TabsTrigger value="usage">Usage</TabsTrigger>
          </TabsList>

          <TabsContent value="playground">
            <p className="text-xs text-muted-foreground">
              Send a test request to verify this provider is reachable and returning data.
            </p>
            <Button size="sm" className="mt-3" onClick={testConnection} disabled={testing}>
              {testing ? <Loader2 className="size-3.5 animate-spin" /> : <PlayCircle className="size-3.5" />}
              {testing ? "Testing…" : "Test Connection"}
            </Button>

            {response && (
              <div className="mt-3 animate-fade-in overflow-hidden rounded-lg border border-border">
                <div className="flex items-center justify-between border-b border-border bg-surface-2/60 px-3 py-1.5">
                  <span className="text-xs font-medium text-success">{response.httpStatus} OK</span>
                  <span className="text-xs text-muted-foreground">{response.latencyMs}ms</span>
                </div>
                <pre className="max-h-56 overflow-auto bg-surface-2/30 p-3 font-mono text-[11px] leading-relaxed text-foreground/90">
                  {JSON.stringify(response.body, null, 2)}
                </pre>
              </div>
            )}
          </TabsContent>

          <TabsContent value="credentials">
            <div className="flex flex-col gap-1.5">
              <Label>API key</Label>
              <div className="flex gap-2">
                <Input readOnly value={maskedKey} className="font-mono text-xs" />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => {
                    navigator.clipboard?.writeText(maskedKey).catch(() => {});
                    toast.success("Copied to clipboard");
                  }}
                >
                  <Copy className="size-3.5" />
                </Button>
              </div>
            </div>
            <Button variant="secondary" size="sm" className="mt-3" onClick={regenerate}>
              <RefreshCcw className="size-3.5" />
              Regenerate key
            </Button>
          </TabsContent>

          <TabsContent value="usage">
            <p className="text-xs text-muted-foreground mb-2">Requests over the last 7 days</p>
            <Sparkline data={sparkline} />
            <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
              {sparkline.map((d) => (
                <span key={d.day}>{d.day}</span>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
