"use client";

import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Building2, Star, ArrowUpRight, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { scoreTone, type PositionedLead } from "@/components/map/map-utils";

export function LeadPreviewCard({
  lead,
  pinned,
  onClose,
}: {
  lead: PositionedLead | null;
  pinned: boolean;
  onClose: () => void;
}) {
  return (
    <AnimatePresence>
      {lead && (
        <motion.div
          key={lead.id}
          initial={{ opacity: 0, scale: 0.92, y: 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.92, y: 6 }}
          transition={{ type: "spring", stiffness: 380, damping: 28 }}
          className={cn(
            "absolute z-30 w-64 glass-strong rounded-xl border border-border-strong p-4 shadow-2xl",
            lead.x < 20 ? "translate-x-0" : lead.x > 80 ? "-translate-x-full" : "-translate-x-1/2",
            lead.y < 28 ? "translate-y-4" : "-translate-y-[calc(100%+18px)]",
          )}
          style={{ left: `${lead.x}%`, top: `${lead.y}%` }}
          onClick={(e) => e.stopPropagation()}
        >
          {pinned && (
            <button
              onClick={onClose}
              className="absolute right-2 top-2 rounded-md p-1 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
              aria-label="Close preview"
            >
              <X className="size-3.5" />
            </button>
          )}
          <div className="flex items-start gap-2.5 pr-4">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
              <Building2 className="size-4 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold leading-tight">{lead.company}</p>
              <p className="truncate text-xs text-muted-foreground">
                {lead.industry} · {lead.city}
              </p>
            </div>
          </div>

          <div className="mt-3 flex items-center gap-2">
            <Badge variant={scoreTone(lead.leadScore)}>Score {lead.leadScore}</Badge>
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Star className="size-3 fill-warning text-warning" />
              {lead.rating.toFixed(1)}
            </span>
            <span className="ml-auto text-[11px] text-muted-foreground">{lead.distanceKm} km away</span>
          </div>

          <Button asChild size="sm" className="mt-3.5 w-full">
            <Link href={`/dashboard/leads/${lead.id}`}>
              View Lead
              <ArrowUpRight className="size-3.5" />
            </Link>
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
