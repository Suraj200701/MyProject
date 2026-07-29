"use client";

import * as React from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface StepLayoutProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onBack?: () => void;
  onNext: () => void;
  nextDisabled?: boolean;
  nextLabel?: string;
  hint?: string;
}

export function StepLayout({
  title,
  subtitle,
  children,
  onBack,
  onNext,
  nextDisabled,
  nextLabel = "Continue",
  hint,
}: StepLayoutProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">{title}</h1>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>

      <div>{children}</div>

      <div className="mt-2 flex items-center justify-between gap-3">
        {onBack ? (
          <Button type="button" variant="ghost" onClick={onBack} className="gap-1.5">
            <ArrowLeft className="size-4" />
            Back
          </Button>
        ) : (
          <span />
        )}
        <div className="flex items-center gap-3">
          {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
          <Button type="button" size="lg" onClick={onNext} disabled={nextDisabled} className="gap-1.5">
            {nextLabel}
            <ArrowRight className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
