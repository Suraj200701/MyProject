"use client";

import { Star } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { Lead, LeadStatus } from "@/lib/types";

const AVATAR_PALETTE = [
  "bg-primary/15 text-primary border-primary/25",
  "bg-accent/15 text-accent border-accent/25",
  "bg-success/15 text-success border-success/25",
  "bg-warning/15 text-warning border-warning/25",
  "bg-danger/15 text-danger border-danger/25",
];

function hashString(value: string) {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function getInitials(company: string) {
  const words = company.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "??";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function CompanyAvatar({ company, className }: { company: string; className?: string }) {
  const palette = AVATAR_PALETTE[hashString(company) % AVATAR_PALETTE.length];
  return (
    <div
      className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold",
        palette,
        className,
      )}
    >
      {getInitials(company)}
    </div>
  );
}

const STATUS_CONFIG: Record<LeadStatus, { label: string; variant: "default" | "primary" | "accent" | "success" | "warning" | "danger" }> = {
  new: { label: "New", variant: "primary" },
  contacted: { label: "Contacted", variant: "warning" },
  qualified: { label: "Qualified", variant: "accent" },
  converted: { label: "Converted", variant: "success" },
  lost: { label: "Lost", variant: "danger" },
};

export function StatusBadge({ status, className }: { status: LeadStatus; className?: string }) {
  const config = STATUS_CONFIG[status];
  return (
    <Badge variant={config.variant} className={className}>
      <span className="size-1.5 rounded-full bg-current" />
      {config.label}
    </Badge>
  );
}

function scoreTone(score: number) {
  if (score >= 75) return { text: "text-success", bg: "bg-success", soft: "bg-success/15 text-success border-success/20" };
  if (score >= 50) return { text: "text-warning", bg: "bg-warning", soft: "bg-warning/15 text-warning border-warning/20" };
  return { text: "text-danger", bg: "bg-danger", soft: "bg-danger/15 text-danger border-danger/20" };
}

export function ScoreBadge({ score }: { score: number }) {
  const tone = scoreTone(score);
  return (
    <div className="flex items-center gap-2 w-[92px]">
      <span className={cn("rounded-full border px-2 py-0.5 text-xs font-semibold tabular-nums", tone.soft)}>{score}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
        <div className={cn("h-full rounded-full", tone.bg)} style={{ width: `${Math.min(100, Math.max(0, score))}%` }} />
      </div>
    </div>
  );
}

export function RatingStars({ rating }: { rating: number }) {
  const rounded = Math.round(rating);
  return (
    <div className="flex items-center gap-1">
      <div className="flex items-center">
        {Array.from({ length: 5 }, (_, i) => (
          <Star
            key={i}
            className={cn(
              "size-3.5",
              i < rounded ? "fill-warning text-warning" : "fill-transparent text-muted-foreground/40",
            )}
          />
        ))}
      </div>
      <span className="text-xs text-muted-foreground tabular-nums">{rating.toFixed(1)}</span>
    </div>
  );
}

export function leadMatchesQuery(lead: Lead, query: string) {
  if (!query) return true;
  return lead.company.toLowerCase().includes(query.toLowerCase());
}
