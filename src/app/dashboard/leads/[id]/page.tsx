"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { formatDistanceToNowStrict } from "date-fns";
import { toast } from "sonner";
import {
  AlertCircle,
  ArrowLeft,
  Building2,
  Check,
  Copy,
  ExternalLink,
  Globe,
  Loader2,
  Mail,
  MapPin,
  Phone,
  ScanLine,
  Sparkles,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { CompanyAvatar, RatingStars, ScoreBadge, StatusBadge } from "@/components/leads/lead-badges";
import { LeadNotes } from "@/components/leads/lead-notes";
import { ApiError, errorMessage } from "@/lib/api/client";
import { exportsApi } from "@/lib/api/endpoints";
import { useLead } from "@/lib/api/queries";

/** Normalizes a stored website value into something safe to put in an href. */
function websiteHref(website: string): string {
  if (!website) return "";
  return /^https?:\/\//i.test(website) ? website : `https://${website}`;
}

export default function LeadProfilePage() {
  const params = useParams<{ id: string }>();
  const leadId = params?.id;
  const { data, isPending, isError, error } = useLead(leadId);
  const [exporting, setExporting] = React.useState(false);

  if (isPending) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-16 w-full max-w-md" />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <div className="space-y-5 lg:col-span-2">
            <Skeleton className="h-56 rounded-xl" />
            <Skeleton className="h-44 rounded-xl" />
            <Skeleton className="h-32 rounded-xl" />
          </div>
          <div className="space-y-5">
            <Skeleton className="h-56 rounded-xl" />
            <Skeleton className="h-56 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (isError || !data) {
    // A 404 means the lead genuinely isn't in this organization; anything else
    // is a transport/server problem and shouldn't claim the lead was deleted.
    const notFound = error instanceof ApiError && error.isNotFound;
    return (
      <div>
        <EmptyState
          icon={notFound ? Building2 : AlertCircle}
          title={notFound ? "Lead not found" : "Couldn't load this lead"}
          description={
            notFound
              ? "This lead may have been removed, or the link is incorrect."
              : errorMessage(error)
          }
        />
        <div className="mt-4 flex justify-center">
          <Button asChild variant="outline" size="sm">
            <Link href="/dashboard/leads">
              <ArrowLeft className="size-3.5" />
              Back to Lead Database
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  const { lead, notes, activities } = data;

  async function handleExport() {
    setExporting(true);
    try {
      const created = await exportsApi.create({
        resource: "leads",
        format: "csv",
        scope: "selected",
        lead_ids: [lead.id],
        file_name: lead.company.replace(/[^\w-]+/g, "_").slice(0, 60) || "lead",
      });
      if (created.status !== "ready") {
        toast.success("Export queued — track it in the Export Center.");
        return;
      }
      window.location.href = await exportsApi.downloadUrl(created.id);
      toast.success("Export ready.");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  return (
    <div>
      <Link
        href="/dashboard/leads"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="size-3.5" />
        Lead Database
      </Link>

      <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-4">
          <CompanyAvatar company={lead.company} className="size-14 text-base" />
          <div>
            <h1 className="text-xl font-semibold tracking-tight">{lead.company}</h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              {lead.industry ? <Badge variant="outline">{lead.industry}</Badge> : null}
              <StatusBadge status={lead.status} />
              <ScoreBadge score={lead.leadScore} />
              {lead.city || lead.country ? (
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <MapPin className="size-3" />
                  {[lead.city, lead.country].filter(Boolean).join(", ")}
                </span>
              ) : null}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Opens the user's mail client — a real action, and the only one
              possible: the backend has no outbound-email-to-lead endpoint. */}
          <Button asChild variant="secondary" size="sm" disabled={!lead.email}>
            <a href={lead.email ? `mailto:${lead.email}` : undefined}>
              <Mail className="size-3.5" />
              Contact
            </a>
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
            {exporting ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <ExternalLink className="size-3.5" />
            )}
            Export
          </Button>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Company Information</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <InfoRow label="Company Type" value={lead.companyType} />
              <InfoRow label="Revenue" value={lead.revenue} />
              <InfoRow label="GST Number" value={lead.gst ?? ""} fallback="Not detected" />
              <InfoRow label="Source Provider" value={lead.provider} fallback="Manual entry" />
              <div>
                <p className="text-xs text-muted-foreground">Website</p>
                {lead.website ? (
                  <a
                    href={websiteHref(lead.website)}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-0.5 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    {lead.website}
                    <ExternalLink className="size-3" />
                  </a>
                ) : (
                  <p className="mt-0.5 text-sm text-muted-foreground">—</p>
                )}
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Rating</p>
                <div className="mt-0.5">
                  {lead.rating > 0 ? (
                    <RatingStars rating={lead.rating} />
                  ) : (
                    <p className="text-sm text-muted-foreground">—</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Contact Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <ContactRow icon={Building2} label="Contact Name" value={lead.contactName} />
              <ContactRow icon={Mail} label="Email" value={lead.email} />
              <ContactRow icon={Phone} label="Phone" value={lead.phone} />
            </CardContent>
          </Card>

          {lead.aiSummary ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-1.5">
                  <Sparkles className="size-4 text-primary" />
                  AI Summary
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border border-primary/20 bg-primary/[0.05] p-4">
                  <p className="text-sm leading-relaxed text-foreground/90">{lead.aiSummary}</p>
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Notes</CardTitle>
            </CardHeader>
            <CardContent>
              <LeadNotes leadId={lead.id} notes={notes} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Tags</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-2">
              {lead.tags.length > 0 ? (
                lead.tags.map((tag) => (
                  <Badge key={tag} variant="primary">
                    {tag}
                  </Badge>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No tags on this lead.</p>
              )}
            </CardContent>
          </Card>

          {/* The "Search History" card was removed: it rendered a template
              string ("{industry} in {city}") as though it were the search that
              found this lead. `LeadOut` carries no search reference, so there is
              nothing truthful to show. Restoring it needs `search_id` on the
              lead detail response. */}
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Location</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex h-32 flex-col items-center justify-center gap-2 rounded-lg border border-border bg-grid bg-surface-2/40">
                <MapPin className="size-5 text-primary" />
                <p className="text-sm font-medium">{lead.city || "Unknown location"}</p>
                <p className="text-xs text-muted-foreground">{lead.country || "—"}</p>
              </div>
              <Button asChild variant="outline" size="sm" className="mt-3 w-full">
                <Link href="/dashboard/map">View on Map</Link>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Lead Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {/* Real activity rows, written by the backend on create / status
                  change / note added. This previously rendered four fixed steps
                  with hardcoded July 2026 timestamps for every lead. */}
              {activities.length === 0 ? (
                <p className="text-sm text-muted-foreground">No activity recorded yet.</p>
              ) : (
                <div className="space-y-0">
                  {activities.map((step, i) => (
                    <div key={step.id} className="relative flex gap-3 pb-5 last:pb-0">
                      {i < activities.length - 1 && (
                        <span className="absolute left-[5px] top-3 h-full w-px bg-border" />
                      )}
                      <span className="relative z-10 mt-1.5 size-2.5 shrink-0 rounded-full bg-primary" />
                      <div>
                        <p className="text-sm text-foreground">{step.description}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatDistanceToNowStrict(new Date(step.created_at), { addSuffix: true })}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Website</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2.5">
                <div className="flex size-9 items-center justify-center rounded-lg border border-border bg-surface-2">
                  <Globe className="size-4 text-muted-foreground" />
                </div>
                {lead.website ? (
                  <a
                    href={websiteHref(lead.website)}
                    target="_blank"
                    rel="noreferrer"
                    className="truncate text-sm font-medium text-primary hover:underline"
                  >
                    {lead.website}
                  </a>
                ) : (
                  <p className="text-sm text-muted-foreground">No website on file</p>
                )}
              </div>
              <Button asChild variant="secondary" size="sm" className="mt-3 w-full">
                {/* Pre-fills the scanner with this lead's domain. */}
                <Link
                  href={
                    lead.website
                      ? `/dashboard/scanner?url=${encodeURIComponent(lead.website)}`
                      : "/dashboard/scanner"
                  }
                >
                  <ScanLine className="size-3.5" />
                  Scan Website
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value, fallback = "—" }: { label: string; value: string; fallback?: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={value ? "mt-0.5 text-sm font-medium text-foreground" : "mt-0.5 text-sm text-muted-foreground"}>
        {value || fallback}
      </p>
    </div>
  );
}

/** Contact row with a copy button that actually copies. */
function ContactRow({ icon: Icon, label, value }: { icon: typeof Mail; label: string; value: string }) {
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access is denied over plain HTTP on some browsers; say so
      // rather than showing a success state that didn't happen.
      toast.error("Couldn't copy — your browser blocked clipboard access.");
    }
  }

  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-surface-2/40 px-3 py-2.5">
      <div className="flex items-center gap-2.5">
        <Icon className="size-4 text-muted-foreground" />
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className={value ? "text-sm text-foreground" : "text-sm text-muted-foreground"}>
            {value || "—"}
          </p>
        </div>
      </div>
      <button
        onClick={copy}
        disabled={!value}
        aria-label={`Copy ${label}`}
        className="rounded-md p-1.5 text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors disabled:opacity-40 disabled:hover:bg-transparent"
      >
        {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
      </button>
    </div>
  );
}
