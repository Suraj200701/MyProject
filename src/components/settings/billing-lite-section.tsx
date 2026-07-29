import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { dashboardStats } from "@/lib/mock-data";

export function BillingLiteSection() {
  const pct = Math.round((dashboardStats.creditsRemaining / dashboardStats.creditsTotal) * 100);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Billing</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border border-border bg-surface-2/40 px-3 py-3">
          <div>
            <p className="text-sm font-semibold">Pro Plan</p>
            <p className="text-xs text-muted-foreground">$249/month · renews Aug 1, 2026</p>
          </div>
          <Badge variant="primary">Active</Badge>
        </div>
        <div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Credits used</span>
            <span>
              {(dashboardStats.creditsTotal - dashboardStats.creditsRemaining).toLocaleString()} /{" "}
              {dashboardStats.creditsTotal.toLocaleString()}
            </span>
          </div>
          <Progress value={100 - pct} className="mt-1.5" />
        </div>
        <Button asChild size="sm" variant="secondary">
          <Link href="/dashboard/billing">Manage Billing</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
