"use client";

import * as React from "react";
import { Loader2, Sparkles, TriangleAlert } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { errorMessage } from "@/lib/api/client";
import { useEnrichLeads } from "@/lib/api/queries";
import type { EnrichmentSummaryOut } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * Bulk contact enrichment for the lead table.
 *
 * Enrichment reads only publicly accessible pages, server-side. Website
 * discovery uses the official Google Places API and only when its key is
 * configured — no key means leads simply keep an empty website, which the
 * summary says out loud rather than implying the businesses have no site.
 *
 * The counters shown are exactly what the backend measured; nothing is inferred
 * here, because a summary that rounds up is worse than no summary.
 */
export function EnrichLeads({
  selectedIds,
  className,
}: {
  selectedIds: string[];
  className?: string;
}) {
  const [summary, setSummary] = React.useState<EnrichmentSummaryOut | null>(null);
  const enrich = useEnrichLeads();

  function run(body: { lead_ids?: string[]; all_unenriched?: boolean }) {
    if (enrich.isPending) return;
    setSummary(null);

    enrich.mutate(body, {
      onSuccess: (data) => {
        setSummary(data);
        if (data.processed === 0) {
          toast.info("Nothing to enrich.", {
            description: "Every selected lead has already been processed.",
          });
          return;
        }
        toast.success(
          `${data.website_found} of ${data.processed} enriched`,
          {
            description: data.discovery_available
              ? `${data.phone_found} phone · ${data.email_found} email · ${data.social_found} social`
              : "Google Places is not configured, so leads without a website were skipped.",
          },
        );
      },
      onError: (error) => toast.error(errorMessage(error)),
    });
  }

  const busy = enrich.isPending;

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          onClick={() => run({ lead_ids: selectedIds })}
          disabled={busy || selectedIds.length === 0}
        >
          {busy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
          Enrich Selected{selectedIds.length > 0 ? ` (${selectedIds.length})` : ""}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => run({ all_unenriched: true })}
          disabled={busy}
          title="Enriches leads that have never been enriched, oldest first"
        >
          Enrich All
        </Button>
        {busy && (
          <span className="text-xs text-muted-foreground">
            Finding websites and reading public contact pages…
          </span>
        )}
      </div>

      {summary && (
        <div className="rounded-xl border border-border bg-card p-3">
          {!summary.discovery_available && (
            <div className="mb-2 flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-2 text-xs">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden />
              <span>
                Google Places isn&apos;t configured, so websites can&apos;t be discovered. Leads that
                already had a website were still enriched.
              </span>
            </div>
          )}

          <dl className="grid grid-cols-3 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-5">
            <Stat label="Total" value={summary.total} />
            <Stat label="Processed" value={summary.processed} />
            <Stat label="Website" value={summary.website_found} tone="success" />
            <Stat label="Phone" value={summary.phone_found} tone="success" />
            <Stat label="Email" value={summary.email_found} tone="success" />
            <Stat label="GST" value={summary.gst_found} tone="success" />
            <Stat label="Social" value={summary.social_found} tone="success" />
            <Stat label="No website" value={summary.no_website} />
            <Stat label="Failed" value={summary.failed} tone={summary.failed ? "danger" : undefined} />
            <Stat label="Credits" value={summary.credits_charged} />
          </dl>

          {summary.results.some((r) => Object.keys(r.field_sources).length > 0) && (
            <div className="mt-3 border-t border-border pt-2">
              <p className="mb-1.5 text-xs font-medium">Where each value came from</p>
              <ul className="space-y-1">
                {summary.results
                  .filter((r) => Object.keys(r.field_sources).length > 0)
                  .slice(0, 8)
                  .flatMap((r) =>
                    Object.entries(r.field_sources).map(([fieldName, url]) => (
                      <li key={`${r.lead_id}-${fieldName}`} className="flex items-center gap-2 text-xs">
                        <Badge variant="outline" className="shrink-0 text-[10px]">
                          {fieldName}
                        </Badge>
                        <a
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="truncate text-muted-foreground underline hover:text-foreground"
                        >
                          {url}
                        </a>
                      </li>
                    )),
                  )}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "success" | "danger";
}) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "tabular-nums font-medium",
          tone === "success" && value > 0 && "text-success",
          tone === "danger" && value > 0 && "text-danger",
        )}
      >
        {value}
      </dd>
    </div>
  );
}
