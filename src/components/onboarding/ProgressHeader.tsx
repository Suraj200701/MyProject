"use client";

import { Progress } from "@/components/ui/progress";

interface ProgressHeaderProps {
  current: number;
  total: number;
}

export function ProgressHeader({ current, total }: ProgressHeaderProps) {
  const percent = Math.round((current / total) * 100);

  return (
    <div className="mb-8 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">
          Step {current} of {total}
        </span>
        <div className="flex items-center gap-1.5">
          {Array.from({ length: total }).map((_, i) => (
            <span
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i + 1 <= current ? "w-5 bg-primary" : "w-1.5 bg-surface-2"
              }`}
            />
          ))}
        </div>
      </div>
      <Progress value={percent} className="h-1" />
    </div>
  );
}
