"use client";

interface TooltipPayloadEntry {
  dataKey?: string | number;
  name?: string | number;
  color?: string;
  value?: number | string;
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string | number;
}

export function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-lg border border-border-strong bg-popover p-2.5 text-xs shadow-xl">
      {label !== undefined && <p className="mb-1.5 font-medium text-popover-foreground">{label}</p>}
      <div className="flex flex-col gap-1">
        {payload.map((entry, i) => (
          <div key={entry.dataKey ?? i} className="flex items-center gap-2">
            <span
              className="size-2 shrink-0 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-muted-foreground">{entry.name}</span>
            <span className="ml-auto font-medium text-popover-foreground">
              {typeof entry.value === "number" ? entry.value.toLocaleString() : entry.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
