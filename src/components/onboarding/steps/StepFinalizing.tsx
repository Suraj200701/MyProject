"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Loader2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CHECKLIST_ITEMS } from "@/components/onboarding/constants";

interface StepFinalizingProps {
  onFinish: () => void;
}

export function StepFinalizing({ onFinish }: StepFinalizingProps) {
  const [completed, setCompleted] = React.useState(0);
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];

    CHECKLIST_ITEMS.forEach((_, index) => {
      timers.push(
        setTimeout(() => {
          setCompleted(index + 1);
        }, (index + 1) * 700),
      );
    });

    timers.push(
      setTimeout(() => {
        setReady(true);
      }, CHECKLIST_ITEMS.length * 700 + 400),
    );

    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="flex flex-col items-center gap-8 py-6 text-center">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Setting up your workspace
        </h1>
        <p className="text-sm text-muted-foreground">
          This will only take a moment. We&apos;re personalizing LeadMaster AI for you.
        </p>
      </div>

      <ul className="flex w-full max-w-xs flex-col gap-3">
        {CHECKLIST_ITEMS.map((label, index) => {
          const isDone = index < completed;
          const isActive = index === completed;
          return (
            <motion.li
              key={label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: isDone || isActive ? 1 : 0.4, y: 0 }}
              transition={{ duration: 0.35 }}
              className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 text-left"
            >
              <span
                className={`flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors duration-300 ${
                  isDone
                    ? "border-success bg-success/15 text-success"
                    : isActive
                      ? "border-primary/40 bg-primary/10 text-primary"
                      : "border-border bg-surface-2 text-muted-foreground"
                }`}
              >
                {isDone ? (
                  <Check className="size-3" strokeWidth={3} />
                ) : isActive ? (
                  <Loader2 className="size-3 animate-spin" />
                ) : null}
              </span>
              <span className={`text-sm ${isDone ? "text-foreground" : "text-muted-foreground"}`}>
                {label}
              </span>
            </motion.li>
          );
        })}
      </ul>

      <AnimatePresence>
        {ready ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <Button type="button" size="lg" variant="gradient" onClick={onFinish} className="gap-1.5 px-8">
              Go to Dashboard
              <ArrowRight className="size-4" />
            </Button>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
