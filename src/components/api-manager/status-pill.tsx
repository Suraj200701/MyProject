import { cn } from "@/lib/utils";
import type { ApiProvider } from "@/lib/types";

const STATUS_CONFIG: Record<ApiProvider["status"], { label: string; dot: string; text: string }> = {
  healthy: { label: "Healthy", dot: "bg-success", text: "text-success" },
  degraded: { label: "Degraded", dot: "bg-warning", text: "text-warning" },
  down: { label: "Down", dot: "bg-danger", text: "text-danger" },
};

export function StatusPill({
  status,
  className,
}: {
  status: ApiProvider["status"];
  className?: string;
}) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xs font-medium",
        config.text,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", config.dot, status === "healthy" && "animate-glow-pulse")} />
      {config.label}
    </span>
  );
}
