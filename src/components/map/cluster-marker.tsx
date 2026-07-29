"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { scoreTone, type MapCluster } from "@/components/map/map-utils";

const TONE_BG: Record<"success" | "warning" | "danger", string> = {
  success: "bg-success text-background border-success/40",
  warning: "bg-warning text-background border-warning/40",
  danger: "bg-danger text-background border-danger/40",
};

export function ClusterMarker({ cluster, onClick }: { cluster: MapCluster; onClick: () => void }) {
  const tone = scoreTone(cluster.avgScore);
  const diameter = Math.min(56, 28 + cluster.count * 3);

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, scale: 0.6 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={{ scale: 1.1 }}
      transition={{ type: "spring", stiffness: 350, damping: 20 }}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="absolute z-10 -translate-x-1/2 -translate-y-1/2 cursor-pointer"
      style={{ left: `${cluster.x}%`, top: `${cluster.y}%` }}
      title={`${cluster.count} leads · avg score ${cluster.avgScore} · click to zoom in`}
    >
      <span className={cn("absolute inset-0 rounded-full opacity-30 blur-md", TONE_BG[tone])} />
      <span
        className={cn(
          "relative flex items-center justify-center rounded-full border-2 font-semibold shadow-lg",
          TONE_BG[tone],
        )}
        style={{ width: diameter, height: diameter, fontSize: diameter > 40 ? 14 : 12 }}
      >
        {cluster.count}
      </span>
    </motion.button>
  );
}
