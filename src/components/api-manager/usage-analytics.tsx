import type { ApiProvider } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export function UsageAnalytics({ providers }: { providers: ApiProvider[] }) {
  const ranked = [...providers].sort((a, b) => b.usage - a.usage);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Usage Analytics</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {ranked.map((provider) => {
          const pct = provider.limit ? Math.round((provider.usage / provider.limit) * 100) : 0;
          return (
            <div key={provider.id}>
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-foreground">
                  {provider.logo} {provider.name}
                </span>
                <span className="tabular-nums text-muted-foreground">
                  {provider.usage.toLocaleString()} req · {pct}%
                </span>
              </div>
              <Progress value={pct} className="mt-1.5" />
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
