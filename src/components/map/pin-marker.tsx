"use client";

import { MapPin } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { scoreTone, type PositionedLead } from "@/components/map/map-utils";

const TONE_CLASSES: Record<"success" | "warning" | "danger", string> = {
  success: "text-success drop-shadow-[0_0_10px_var(--color-success)]",
  warning: "text-warning drop-shadow-[0_0_10px_var(--color-warning)]",
  danger: "text-danger drop-shadow-[0_0_10px_var(--color-danger)]",
};

const TONE_RING: Record<"success" | "warning" | "danger", string> = {
  success: "bg-success/30",
  warning: "bg-warning/30",
  danger: "bg-danger/30",
};

export function PinMarker({
  lead,
  active,
  onHoverStart,
  onHoverEnd,
  onSelect,
}: {
  lead: PositionedLead;
  active: boolean;
  onHoverStart: () => void;
  onHoverEnd: () => void;
  onSelect: () => void;
}) {
  const tone = scoreTone(lead.leadScore);
  const size = lead.leadScore >= 80 ? "size-6" : lead.leadScore >= 60 ? "size-5" : "size-4";

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.25 }}
      transition={{ type: "spring", stiffness: 400, damping: 22 }}
      onMouseEnter={onHoverStart}
      onMouseLeave={onHoverEnd}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      className="absolute z-10 -translate-x-1/2 -translate-y-full cursor-pointer"
      style={{ left: `${lead.x}%`, top: `${lead.y}%` }}
      aria-label={lead.company}
    >
      {active && (
        <span className={cn("absolute inset-0 -z-10 rounded-full animate-ping", TONE_RING[tone])} />
      )}
      <MapPin
        className={cn(size, TONE_CLASSES[tone], "transition-transform", active && "scale-125")}
        fill="currentColor"
        fillOpacity={0.18}
        strokeWidth={2}
      />
    </motion.button>
  );
}
