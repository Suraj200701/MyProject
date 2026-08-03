"use client";

import { ScanLine } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { AsyncContent, SkeletonRows } from "@/components/shared/async-content";
import { useScans } from "@/lib/api/queries";

/**
 * Which "field found" chips to show for a scan.
 *
 * Derived from what the scan actually extracted, so a chip is only present when
 * the corresponding value exists on the record — the previous hardcoded list
 * showed "GST Found" for companies that were never scanned.
 */
function foundFields(scan: {
  gst_number: string | null;
  gst_verified: boolean;
  emails: string[] | null;
  phones: string[] | null;
  social_links: { found: boolean }[] | null;
}): string[] {
  const fields: string[] = [];
  if (scan.gst_number) fields.push(scan.gst_verified ? "GST Verified" : "GST Found");
  if (scan.emails?.length) fields.push(`${scan.emails.length} Email${scan.emails.length > 1 ? "s" : ""}`);
  if (scan.phones?.length) fields.push(`${scan.phones.length} Phone${scan.phones.length > 1 ? "s" : ""}`);
  const socials = (scan.social_links ?? []).filter((s) => s.found).length;
  if (socials > 0) fields.push(`${socials} Social`);
  return fields;
}

export function WebsiteScanResults() {
  const { data, isPending, isError, error } = useScans({ page_size: 4 });
  const scans = data?.items ?? [];

  return (
    <Card className="glass overflow-hidden">
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <div className="flex size-7 items-center justify-center rounded-lg bg-accent/15 text-accent">
          <ScanLine className="size-3.5" />
        </div>
        <CardTitle>Website Scan Results</CardTitle>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={scans.length === 0}
        emptyMessage="No websites scanned yet."
        className="min-h-[200px] p-5"
        skeleton={<SkeletonRows rows={3} />}
      >
        <div className="flex flex-col divide-y divide-border p-5 pt-3">
          {scans.map((scan) => {
            const fields = foundFields(scan);
            return (
              <div key={scan.id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground/90">
                      {scan.company_name || scan.domain}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">{scan.domain}</p>
                  </div>
                  <span className="shrink-0 text-xs font-medium tabular-nums text-muted-foreground">
                    {scan.confidence_score}%
                  </span>
                </div>
                <Progress value={scan.confidence_score} />
                <div className="flex flex-wrap gap-1.5">
                  {fields.length > 0 ? (
                    fields.map((field) => (
                      <Badge key={field} variant="success" className="text-[11px]">
                        {field}
                      </Badge>
                    ))
                  ) : (
                    <Badge variant="warning" className="text-[11px]">
                      No contact details found
                    </Badge>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </AsyncContent>
      <div className="border-t border-border px-5 py-3">
        <Link href="/dashboard/scanner" className="text-xs font-medium text-primary hover:underline">
          Scan another website
        </Link>
      </div>
    </Card>
  );
}
