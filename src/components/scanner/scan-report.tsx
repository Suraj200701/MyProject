"use client";

import { formatDistanceToNowStrict } from "date-fns";
import {
  BadgeCheck,
  Camera,
  Clock,
  Link2,
  Mail,
  Phone,
  RotateCcw,
  ShieldCheck,
  Smartphone,
  Square,
  Timer,
  X as XIcon,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import type { ScanReport, SocialResult } from "@/components/scanner/types";
import { cn } from "@/lib/utils";

const SOCIAL_ICON: Record<SocialResult["platform"], typeof Link2> = {
  LinkedIn: Link2,
  Facebook: Square,
  Instagram: Camera,
  X: XIcon,
};

function scoreTone(score: number) {
  if (score >= 80) return "success" as const;
  if (score >= 55) return "warning" as const;
  return "danger" as const;
}

export function ScanReportView({ report, onReset }: { report: ScanReport; onReset: () => void }) {
  const tone = scoreTone(report.confidence);

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="flex flex-col items-center gap-4 p-6 sm:flex-row sm:justify-between">
          <div className="flex items-center gap-4">
            <div
              className={cn(
                "flex size-20 shrink-0 items-center justify-center rounded-full border-4 text-xl font-bold",
                tone === "success" && "border-success/40 text-success",
                tone === "warning" && "border-warning/40 text-warning",
                tone === "danger" && "border-danger/40 text-danger",
              )}
            >
              {report.confidence}%
            </div>
            <div>
              <p className="text-sm font-semibold">{report.companyName || report.domain}</p>
              <p className="text-xs text-muted-foreground">{report.domain}</p>
              <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <Timer className="size-3" />
                  {(report.scanDurationMs / 1000).toFixed(1)}s scan
                </span>
                <span className="inline-flex items-center gap-1">
                  <Clock className="size-3" />
                  {formatDistanceToNowStrict(new Date(report.scannedAt), { addSuffix: true })}
                </span>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => toast.success("Saved to lead profile")}>
              <BadgeCheck className="size-3.5" />
              Save to Lead
            </Button>
            <Button variant="secondary" size="sm" onClick={() => toast.success("Report exported")}>
              Export Report
            </Button>
            <Button variant="outline" size="sm" onClick={onReset}>
              <RotateCcw className="size-3.5" />
              Scan another
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Mail className="size-4 text-primary" />
              Contact Extraction
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {report.contacts.emails.map((email) => (
              <div key={email} className="flex items-center gap-2 rounded-lg border border-border bg-surface-2/40 px-3 py-2 text-sm">
                <Mail className="size-3.5 text-muted-foreground" />
                {email}
              </div>
            ))}
            {report.contacts.phones.map((phone) => (
              <div key={phone} className="flex items-center gap-2 rounded-lg border border-border bg-surface-2/40 px-3 py-2 text-sm">
                <Phone className="size-3.5 text-muted-foreground" />
                {phone}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <ShieldCheck className="size-4 text-primary" />
              GST / Business ID Detection
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border border-border bg-surface-2/40 px-3 py-3">
              <p className="font-mono text-sm">{report.gst.number}</p>
              <Badge variant={report.gst.verifiedFormat ? "success" : "outline"} className="mt-2">
                {report.gst.verifiedFormat ? "Verified format" : "Not detected"}
              </Badge>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">Registered contact: {report.contactPerson}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Social Media Detection</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2">
            {report.social.map((s) => {
              const Icon = SOCIAL_ICON[s.platform];
              return (
                <div
                  key={s.platform}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                    s.found ? "border-success/25 bg-success/[0.06] text-foreground" : "border-border bg-surface-2/30 text-muted-foreground",
                  )}
                >
                  <Icon className="size-3.5" />
                  <span className="flex-1">{s.platform}</span>
                  {s.found ? (
                    <span className="text-xs text-success">{s.handle}</span>
                  ) : (
                    <span className="text-xs">Not found</span>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              <Zap className="size-4 text-primary" />
              Website Health
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            <HealthRow label="SSL Certificate" ok={report.health.ssl} />
            <HealthRow label="Mobile Friendly" ok={report.health.mobileFriendly} icon={Smartphone} />
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Load Time</span>
              <span className="font-medium">{(report.health.loadTimeMs / 1000).toFixed(2)}s</span>
            </div>
            <div>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>SEO Score</span>
                <span>{report.health.seoScore}/100</span>
              </div>
              <Progress value={report.health.seoScore} className="mt-1" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Timeline View</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-0">
            {report.stages.map((stage, i) => (
              <div key={stage.id} className="relative flex gap-3 pb-4 last:pb-0">
                {i < report.stages.length - 1 && (
                  <span className="absolute left-[5px] top-3 h-full w-px bg-border" />
                )}
                <span className="relative z-10 mt-1.5 size-2.5 shrink-0 rounded-full bg-success" />
                <div className="flex flex-1 items-center justify-between">
                  <p className="text-sm text-foreground">{stage.label}</p>
                  <p className="text-xs text-muted-foreground">{(stage.durationMs / 1000).toFixed(2)}s</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function HealthRow({ label, ok, icon: Icon = ShieldCheck }: { label: string; ok: boolean; icon?: typeof ShieldCheck }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="inline-flex items-center gap-1.5 text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </span>
      <Badge variant={ok ? "success" : "danger"}>{ok ? "Passed" : "Failed"}</Badge>
    </div>
  );
}
