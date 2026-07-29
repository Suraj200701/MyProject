import { formatDistanceToNowStrict } from "date-fns";
import { Globe } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { RecentScan } from "@/components/scanner/types";

function tone(score: number) {
  if (score >= 80) return "success" as const;
  if (score >= 55) return "warning" as const;
  return "danger" as const;
}

export function RecentScans({ scans, onSelect }: { scans: RecentScan[]; onSelect: (domain: string) => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Scans</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        {scans.map((scan) => (
          <button
            key={scan.id}
            onClick={() => onSelect(scan.domain)}
            className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left transition-colors hover:bg-surface-2/60"
          >
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
              <Globe className="size-3.5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{scan.domain}</p>
              <p className="text-xs text-muted-foreground">
                {formatDistanceToNowStrict(new Date(scan.scannedAt), { addSuffix: true })}
              </p>
            </div>
            <Badge variant={tone(scan.confidence)}>{scan.confidence}%</Badge>
          </button>
        ))}
      </CardContent>
    </Card>
  );
}
