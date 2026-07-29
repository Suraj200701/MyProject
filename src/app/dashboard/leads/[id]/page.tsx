import Link from "next/link";
import { formatDistanceToNowStrict } from "date-fns";
import {
  ArrowLeft,
  Building2,
  Copy,
  ExternalLink,
  Globe,
  Mail,
  MapPin,
  Phone,
  ScanLine,
  Sparkles,
  Tag as TagIcon,
} from "lucide-react";

import { mockLeads } from "@/lib/mock-data";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { CompanyAvatar, RatingStars, ScoreBadge, StatusBadge } from "@/components/leads/lead-badges";
import { LeadNotes } from "@/components/leads/lead-notes";

const TIMELINE_TEMPLATE = [
  { label: "Discovered via {provider}", at: "2026-07-17T08:00:00.000Z" },
  { label: "AI lead score calculated", at: "2026-07-17T08:05:00.000Z" },
  { label: "Added to lead database", at: "2026-07-18T09:00:00.000Z" },
  { label: "Contact details enriched", at: "2026-07-23T14:30:00.000Z" },
];

const SEARCH_HISTORY_TEMPLATE = [
  { label: "{industry} in {city}", resultsHint: "surfaced this lead" },
];

export default async function LeadProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const lead = mockLeads.find((l) => l.id === id);

  if (!lead) {
    return (
      <div>
        <EmptyState
          icon={Building2}
          title="Lead not found"
          description="This lead may have been removed or the link is incorrect."
          actionLabel="Back to Lead Database"
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
              <Badge variant="outline">{lead.industry}</Badge>
              <StatusBadge status={lead.status} />
              <ScoreBadge score={lead.leadScore} />
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <MapPin className="size-3" />
                {lead.city}, {lead.country}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm">
            <Mail className="size-3.5" />
            Contact
          </Button>
          <Button variant="secondary" size="sm">
            <TagIcon className="size-3.5" />
            Add Note
          </Button>
          <Button variant="outline" size="sm">
            <ExternalLink className="size-3.5" />
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
              <InfoRow label="GST Number" value={lead.gst ?? "Not detected"} />
              <InfoRow label="Source Provider" value={lead.provider} />
              <div>
                <p className="text-xs text-muted-foreground">Website</p>
                <a
                  href={`https://${lead.website}`}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-0.5 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                >
                  {lead.website}
                  <ExternalLink className="size-3" />
                </a>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Rating</p>
                <div className="mt-0.5">
                  <RatingStars rating={lead.rating} />
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

          <Card>
            <CardHeader>
              <CardTitle>Notes</CardTitle>
            </CardHeader>
            <CardContent>
              <LeadNotes leadId={lead.id} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Tags</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-2">
              {lead.tags.map((tag) => (
                <Badge key={tag} variant="primary">
                  {tag}
                </Badge>
              ))}
              <button className="rounded-full border border-dashed border-border px-2.5 py-0.5 text-xs text-muted-foreground hover:border-border-strong hover:text-foreground transition-colors">
                + Add tag
              </button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Search History</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {SEARCH_HISTORY_TEMPLATE.map((item, i) => (
                <div key={i} className="flex items-center justify-between rounded-lg border border-border bg-surface-2/40 px-3 py-2">
                  <p className="text-sm text-foreground">
                    {item.label.replace("{industry}", lead.industry).replace("{city}", lead.city)}
                  </p>
                  <p className="text-xs text-muted-foreground">{item.resultsHint}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>Location</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex h-32 flex-col items-center justify-center gap-2 rounded-lg border border-border bg-grid bg-surface-2/40">
                <MapPin className="size-5 text-primary" />
                <p className="text-sm font-medium">{lead.city}</p>
                <p className="text-xs text-muted-foreground">{lead.country}</p>
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
              <div className="space-y-0">
                {TIMELINE_TEMPLATE.map((step, i) => (
                  <div key={i} className="relative flex gap-3 pb-5 last:pb-0">
                    {i < TIMELINE_TEMPLATE.length - 1 && (
                      <span className="absolute left-[5px] top-3 h-full w-px bg-border" />
                    )}
                    <span className="relative z-10 mt-1.5 size-2.5 shrink-0 rounded-full bg-primary" />
                    <div>
                      <p className="text-sm text-foreground">{step.label.replace("{provider}", lead.provider)}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDistanceToNowStrict(new Date(step.at), { addSuffix: true })}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
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
                <a
                  href={`https://${lead.website}`}
                  target="_blank"
                  rel="noreferrer"
                  className="truncate text-sm font-medium text-primary hover:underline"
                >
                  {lead.website}
                </a>
              </div>
              <Button asChild variant="secondary" size="sm" className="mt-3 w-full">
                <Link href="/dashboard/scanner">
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

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}

function ContactRow({ icon: Icon, label, value }: { icon: typeof Mail; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-surface-2/40 px-3 py-2.5">
      <div className="flex items-center gap-2.5">
        <Icon className="size-4 text-muted-foreground" />
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-sm text-foreground">{value}</p>
        </div>
      </div>
      <button className="rounded-md p-1.5 text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors">
        <Copy className="size-3.5" />
      </button>
    </div>
  );
}
