"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Star, MapPin, ArrowUpRight, Building2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { Lead } from "@/lib/types";

function scoreVariant(score: number): "success" | "warning" | "danger" {
  if (score > 75) return "success";
  if (score >= 50) return "warning";
  return "danger";
}

export function ResultCard({
  lead,
  selected,
  onToggleSelect,
  index,
}: {
  lead: Lead;
  selected: boolean;
  onToggleSelect: (id: string) => void;
  index: number;
}) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(index, 12) * 0.03, ease: "easeOut" }}
    >
      <Card
        className={cn(
          "relative p-4 h-full flex flex-col gap-3 hover:border-border-strong transition-colors",
          selected && "border-primary/50 bg-primary/[0.03]",
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2.5 min-w-0">
            <Checkbox
              checked={selected}
              onCheckedChange={() => onToggleSelect(lead.id)}
              className="mt-1 shrink-0"
              aria-label={`Select ${lead.company}`}
            />
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate">{lead.company}</p>
              <div className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                <MapPin className="size-3 shrink-0" />
                <span className="truncate">
                  {lead.city}, {lead.country}
                </span>
              </div>
            </div>
          </div>
          <Badge variant={scoreVariant(lead.leadScore)} className="shrink-0">
            {lead.leadScore}
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline" className="gap-1">
            <Building2 className="size-3" />
            {lead.industry}
          </Badge>
          <Badge variant="default">{lead.companyType}</Badge>
        </div>

        <div className="flex items-center gap-1">
          {Array.from({ length: 5 }).map((_, i) => (
            <Star
              key={i}
              className={cn(
                "size-3.5",
                i < Math.round(lead.rating)
                  ? "fill-warning text-warning"
                  : "text-border-strong",
              )}
            />
          ))}
          <span className="text-xs text-muted-foreground ml-1">{lead.rating.toFixed(1)}</span>
        </div>

        <p className="text-xs text-muted-foreground line-clamp-2">{lead.aiSummary}</p>

        <div className="mt-auto flex items-center justify-between pt-2 border-t border-border">
          <span className="text-xs text-muted-foreground">via {lead.provider}</span>
          <Button asChild size="sm" variant="secondary">
            <Link href={`/dashboard/leads/${lead.id}`}>
              View
              <ArrowUpRight className="size-3.5" />
            </Link>
          </Button>
        </div>
      </Card>
    </motion.div>
  );
}
