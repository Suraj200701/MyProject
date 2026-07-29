"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChipToggleProps {
  label: string;
  selected: boolean;
  onClick: () => void;
  prefix?: React.ReactNode;
  className?: string;
}

export function ChipToggle({ label, selected, onClick, prefix, className }: ChipToggleProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium transition-all duration-200",
        selected
          ? "border-primary/30 bg-primary/15 text-primary shadow-[0_0_16px_-6px_var(--color-primary)]"
          : "border-border bg-surface-2 text-muted-foreground hover:border-border-strong hover:text-foreground",
        className,
      )}
    >
      {prefix ? <span className="leading-none">{prefix}</span> : null}
      <span>{label}</span>
      {selected ? <Check className="size-3.5" strokeWidth={3} /> : null}
    </button>
  );
}
