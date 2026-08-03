"use client";

/**
 * Loading / error / empty states for data-backed panels.
 *
 * Exists so those three states are written once instead of ~30 times, and so
 * they all occupy the **same box** as the loaded content. That matters more than
 * it sounds: a chart card whose skeleton is a different height makes the whole
 * dashboard reflow as each query resolves.
 *
 * Purely additive — it wraps existing content and changes no card, chart or
 * table styling.
 */

import * as React from "react";
import { AlertCircle, Inbox, Loader2 } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface AsyncContentProps {
  isPending: boolean;
  isError?: boolean;
  error?: unknown;
  /** Render the empty state instead of children. */
  isEmpty?: boolean;
  emptyMessage?: string;
  /** Tailwind height class matching the loaded content, e.g. "h-64". */
  className?: string;
  /** Custom skeleton; defaults to a single block filling `className`. */
  skeleton?: React.ReactNode;
  children: React.ReactNode;
}

/** Best-effort message from an unknown thrown value. */
function messageFor(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "Something went wrong.";
}

export function AsyncContent({
  isPending,
  isError,
  error,
  isEmpty,
  emptyMessage = "Nothing to show yet.",
  className,
  skeleton,
  children,
}: AsyncContentProps) {
  if (isPending) {
    return (
      <div className={cn("w-full", className)} role="status" aria-busy="true">
        {skeleton ?? <Skeleton className="size-full rounded-lg" />}
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 px-4 text-center",
          className,
        )}
        role="alert"
      >
        <AlertCircle className="size-5 text-warning" />
        <p className="text-sm text-muted-foreground">{messageFor(error)}</p>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 px-4 text-center",
          className,
        )}
      >
        <Inbox className="size-5 text-muted-foreground/60" />
        <p className="text-sm text-muted-foreground">{emptyMessage}</p>
      </div>
    );
  }

  return <>{children}</>;
}

/** Small inline spinner for buttons and row-level actions. */
export function InlineSpinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} />;
}

/** Stack of skeleton rows, for list panels. */
export function SkeletonRows({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 rounded-lg" />
      ))}
    </div>
  );
}
