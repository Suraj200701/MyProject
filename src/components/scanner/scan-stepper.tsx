"use client";

import { Check, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { ScanStageState } from "@/components/scanner/types";

export function ScanStepper({ stages, overallProgress }: { stages: ScanStageState[]; overallProgress: number }) {
  return (
    <div>
      <div className="mb-4">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Scanning in progress</span>
          <span className="tabular-nums">{overallProgress}%</span>
        </div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2">
          <motion.div
            className="h-full rounded-full bg-[linear-gradient(90deg,var(--color-primary),var(--color-accent))]"
            animate={{ width: `${overallProgress}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </div>

      <div className="space-y-1">
        {stages.map((stage) => (
          <div
            key={stage.id}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors",
              stage.status === "active" && "bg-primary/[0.06]",
            )}
          >
            <span
              className={cn(
                "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs",
                stage.status === "done" && "border-success/40 bg-success/15 text-success",
                stage.status === "active" && "border-primary/40 bg-primary/15 text-primary",
                stage.status === "pending" && "border-border bg-surface-2 text-muted-foreground",
              )}
            >
              {stage.status === "done" ? (
                <Check className="size-3.5" />
              ) : stage.status === "active" ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <span className="size-1.5 rounded-full bg-current" />
              )}
            </span>
            <div className="min-w-0">
              <p
                className={cn(
                  "text-sm",
                  stage.status === "pending" ? "text-muted-foreground" : "text-foreground font-medium",
                )}
              >
                {stage.label}
              </p>
              <p className="text-xs text-muted-foreground">{stage.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
