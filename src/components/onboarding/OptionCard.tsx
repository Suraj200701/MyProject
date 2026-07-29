"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface OptionCardProps {
  label: string;
  description?: string;
  icon?: React.ReactNode;
  selected: boolean;
  onClick: () => void;
  className?: string;
}

export function OptionCard({ label, description, icon, selected, onClick, className }: OptionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "group relative flex w-full items-center gap-3 rounded-xl border p-4 text-left transition-all duration-200 cursor-pointer",
        selected
          ? "border-primary bg-primary/10 ring-1 ring-primary/40 shadow-[0_0_24px_-8px_var(--color-primary)]"
          : "border-border bg-card hover:border-border-strong hover:bg-surface-2",
        className,
      )}
    >
      {icon ? (
        <span
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-lg border text-lg transition-colors",
            selected
              ? "border-primary/30 bg-primary/15 text-primary"
              : "border-border bg-surface-2 text-muted-foreground group-hover:text-foreground",
          )}
        >
          {icon}
        </span>
      ) : null}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className={cn("truncate text-sm font-medium", selected ? "text-foreground" : "text-foreground")}>
          {label}
        </span>
        {description ? (
          <span className="truncate text-xs text-muted-foreground">{description}</span>
        ) : null}
      </span>
      <span
        className={cn(
          "flex size-5 shrink-0 items-center justify-center rounded-full border transition-all duration-200",
          selected
            ? "border-primary bg-primary text-primary-foreground scale-100 opacity-100"
            : "border-border bg-transparent scale-90 opacity-0 group-hover:opacity-60",
        )}
      >
        <Check className="size-3" strokeWidth={3} />
      </span>
    </button>
  );
}
