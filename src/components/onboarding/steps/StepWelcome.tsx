"use client";

import { Sparkles, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface StepWelcomeProps {
  onNext: () => void;
}

export function StepWelcome({ onNext }: StepWelcomeProps) {
  return (
    <div className="flex flex-col items-center gap-6 py-6 text-center">
      <div className="glow-ring flex size-16 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--color-primary),var(--color-accent))] text-white shadow-[0_0_40px_-8px_var(--color-primary)]">
        <Sparkles className="size-8" />
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium text-muted-foreground">LeadMaster AI</span>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          Welcome to <span className="text-gradient">LeadMaster AI</span>
        </h1>
        <p className="mx-auto max-w-sm text-base text-muted-foreground">
          Let&apos;s set up your workspace. A few quick questions will help us personalize your
          lead intelligence experience.
        </p>
      </div>

      <Button type="button" size="lg" variant="gradient" onClick={onNext} className="mt-2 gap-1.5 px-8">
        Get Started
        <ArrowRight className="size-4" />
      </Button>
    </div>
  );
}
