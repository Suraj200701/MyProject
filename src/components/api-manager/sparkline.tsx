import type { SparklineDay } from "@/components/api-manager/mock-extras";

export function Sparkline({ data }: { data: SparklineDay[] }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="flex h-12 items-end gap-1">
      {data.map((d) => (
        <div key={d.day} className="flex flex-1 flex-col items-center gap-1">
          <div
            className="w-full rounded-sm bg-[linear-gradient(180deg,var(--color-primary),var(--color-accent))] opacity-80"
            style={{ height: `${Math.max(6, (d.value / max) * 100)}%` }}
            title={`${d.day}: ${d.value}`}
          />
        </div>
      ))}
    </div>
  );
}
