import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiProviders } from "@/lib/mock-data";

const STATUS_VARIANT = { healthy: "success", degraded: "warning", down: "danger" } as const;

export function ProvidersSection() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Providers</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          Manage connections, credentials, and health in the full API Manager.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {apiProviders.map((p) => (
            <span
              key={p.id}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-2/60 px-2.5 py-1 text-xs"
            >
              {p.logo} {p.name}
              <span
                className={`size-1.5 rounded-full ${
                  STATUS_VARIANT[p.status] === "success"
                    ? "bg-success"
                    : STATUS_VARIANT[p.status] === "warning"
                      ? "bg-warning"
                      : "bg-danger"
                }`}
              />
            </span>
          ))}
        </div>
        <Button asChild size="sm" variant="secondary">
          <Link href="/dashboard/api-manager">Manage in API Manager</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
