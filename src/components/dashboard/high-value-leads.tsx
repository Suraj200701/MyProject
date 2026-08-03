"use client";

import { ArrowUpRight, Star } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { useLeads } from "@/lib/api/queries";
import { AsyncContent, SkeletonRows } from "@/components/shared/async-content";

function scoreVariant(score: number): "success" | "primary" | "warning" {
  if (score >= 80) return "success";
  if (score >= 60) return "primary";
  return "warning";
}

export function HighValueLeads() {
  // Sorted and limited server-side rather than fetching every lead to slice five.
  const { data, isPending, isError, error } = useLeads({
    page_size: 5,
    sort_by: "lead_score",
    sort_order: "desc",
  });
  const topLeads = data?.items ?? [];

  return (
    <Card className="glass overflow-hidden">
      <CardHeader className="flex-row items-center gap-2 space-y-0">
        <div className="flex size-7 items-center justify-center rounded-lg bg-warning/15 text-warning">
          <Star className="size-3.5" />
        </div>
        <CardTitle>High Value Leads</CardTitle>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={topLeads.length === 0}
        emptyMessage="No leads yet — run a search or import a CSV."
        className="min-h-[180px] p-5"
        skeleton={<SkeletonRows rows={4} />}
      >
      <div className="flex flex-col divide-y divide-border p-5 pt-3">
        {topLeads.map((lead) => (
          <Link
            key={lead.id}
            href={`/dashboard/leads/${lead.id}`}
            className="group flex items-center gap-3 py-3 first:pt-0 last:pb-0"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground/90">{lead.company}</p>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {lead.industry} · {lead.city}, {lead.country}
              </p>
            </div>
            <Badge variant={scoreVariant(lead.leadScore)} className="shrink-0">
              {lead.leadScore}
            </Badge>
            <ArrowUpRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-primary" />
          </Link>
        ))}
      </div>
      </AsyncContent>
      <div className="border-t border-border px-5 py-3">
        <Link href="/dashboard/leads" className="text-xs font-medium text-primary hover:underline">
          View all leads
        </Link>
      </div>
    </Card>
  );
}
