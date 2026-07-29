"use client";

import { Lock } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import type { ScanStageState } from "@/components/scanner/types";

export function BrowserMock({ url, stages }: { url: string; stages: ScanStageState[] }) {
  const contactsRevealed = stages.find((s) => s.id === "contacts")?.status === "done";
  const gstRevealed = stages.find((s) => s.id === "gst")?.status === "done";
  const socialRevealed = stages.find((s) => s.id === "social")?.status === "done";

  return (
    <div className="overflow-hidden rounded-xl border border-border-strong">
      <div className="flex items-center gap-2 border-b border-border bg-surface-2/70 px-3 py-2">
        <div className="flex gap-1.5">
          <span className="size-2.5 rounded-full bg-danger/60" />
          <span className="size-2.5 rounded-full bg-warning/60" />
          <span className="size-2.5 rounded-full bg-success/60" />
        </div>
        <div className="ml-2 flex flex-1 items-center gap-1.5 rounded-md bg-surface px-2 py-1 text-xs text-muted-foreground">
          <Lock className="size-3" />
          <span className="truncate">{url || "https://example.com"}</span>
        </div>
      </div>

      <div className="space-y-3 bg-surface-2/20 p-4">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-5/6" />

        <div className="rounded-lg border border-border bg-surface/60 p-3">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Contacts</p>
          {contactsRevealed ? (
            <p className="animate-fade-in text-xs text-foreground">Email &amp; phone detected on page</p>
          ) : (
            <Skeleton className="h-3 w-1/2" />
          )}
        </div>

        <div className="rounded-lg border border-border bg-surface/60 p-3">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Business ID</p>
          {gstRevealed ? (
            <p className="animate-fade-in text-xs text-foreground">GST pattern matched in footer</p>
          ) : (
            <Skeleton className="h-3 w-2/5" />
          )}
        </div>

        <div className="rounded-lg border border-border bg-surface/60 p-3">
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Social Links</p>
          {socialRevealed ? (
            <p className="animate-fade-in text-xs text-foreground">Profile links found in header/footer</p>
          ) : (
            <Skeleton className="h-3 w-3/5" />
          )}
        </div>
      </div>
    </div>
  );
}
