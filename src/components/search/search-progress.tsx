"use client";

import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, Loader2, Circle, Clock, Users } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ProviderRun } from "@/components/search/types";

export function SearchProgress({
  providers,
  overallProgress,
  elapsedMs,
  leadsFound,
  query,
}: {
  providers: ProviderRun[];
  overallProgress: number;
  elapsedMs: number;
  leadsFound: number;
  query: string;
}) {
  const elapsedSeconds = (elapsedMs / 1000).toFixed(1);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <Card className="glass-strong border-border-strong overflow-hidden relative">
        <div className="absolute inset-0 shimmer-bg opacity-30 pointer-events-none" />
        <CardContent className="relative pt-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <p className="text-sm font-medium">
                Searching for <span className="text-primary">&ldquo;{query || "leads"}&rdquo;</span>
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Scanning connected data providers in real time…
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Clock className="size-3.5" />
                {elapsedSeconds}s
              </div>
              <div className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                <Users className="size-3.5 text-primary" />
                <motion.span
                  key={leadsFound}
                  initial={{ scale: 1.15, color: "var(--color-primary)" }}
                  animate={{ scale: 1, color: "var(--color-foreground)" }}
                  transition={{ duration: 0.3 }}
                >
                  {leadsFound}
                </motion.span>
                <span className="text-muted-foreground font-normal">leads found</span>
              </div>
            </div>
          </div>

          <Progress value={overallProgress} />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <AnimatePresence initial={false}>
              {providers.map((p) => (
                <motion.div
                  key={p.id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "flex items-center gap-3 rounded-xl border border-border bg-surface-2/50 px-3.5 py-3 transition-colors",
                    p.status === "searching" && "border-primary/30",
                    p.status === "done" && "border-success/30",
                  )}
                >
                  <div className="shrink-0">
                    {p.status === "pending" && <Circle className="size-4 text-muted-foreground" />}
                    {p.status === "searching" && (
                      <Loader2 className="size-4 text-primary animate-spin" />
                    )}
                    {p.status === "done" && <CheckCircle2 className="size-4 text-success" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium truncate">{p.name}</p>
                      {p.status === "done" ? (
                        <Badge variant="success" className="shrink-0">
                          {p.found} found
                        </Badge>
                      ) : p.status === "searching" ? (
                        <span className="text-xs text-muted-foreground shrink-0">{p.progress}%</span>
                      ) : (
                        <span className="text-xs text-muted-foreground shrink-0">Queued</span>
                      )}
                    </div>
                    <Progress value={p.progress} className="h-1 mt-2" />
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
