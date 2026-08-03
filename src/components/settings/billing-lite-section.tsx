"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useSubscription, useUsage } from "@/lib/api/queries";
import { formatDate, formatMoney } from "@/components/billing/format";

export function BillingLiteSection() {
  const subscription = useSubscription();
  const usage = useUsage();

  const plan = subscription.data?.plan ?? null;
  const renewsAt = subscription.data?.current_period_end ?? null;

  // Guarded: a plan with no credit allowance would otherwise render NaN%.
  const usedPct =
    usage.data && usage.data.credits_limit > 0
      ? Math.min(100, Math.round((usage.data.credits_used / usage.data.credits_limit) * 100))
      : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Billing</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between rounded-lg border border-border bg-surface-2/40 px-3 py-3">
          <div>
            {subscription.isPending ? (
              <Skeleton className="h-5 w-32" />
            ) : (
              <p className="text-sm font-semibold">{plan ? `${plan.name} Plan` : "No plan"}</p>
            )}
            <p className="text-xs text-muted-foreground">
              {plan
                ? [
                    `${formatMoney(plan.price_cents, plan.currency)}/${plan.billing_interval}`,
                    renewsAt ? `renews ${formatDate(renewsAt)}` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : "Subscribe to unlock more credits"}
            </p>
          </div>
          {subscription.data?.status ? (
            <Badge variant={subscription.data.status === "active" ? "primary" : "outline"}>
              {subscription.data.status.charAt(0).toUpperCase() + subscription.data.status.slice(1)}
            </Badge>
          ) : null}
        </div>
        <div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Credits used</span>
            <span>
              {usage.data
                ? `${usage.data.credits_used.toLocaleString()} / ${usage.data.credits_limit.toLocaleString()}`
                : "—"}
            </span>
          </div>
          {/* The bar shows consumption, matching the "Credits used" label —
              the previous version passed the *remaining* percentage, so a
              nearly-exhausted balance rendered as a nearly-full bar. */}
          <Progress value={usedPct} className="mt-1.5" />
        </div>
        <Button asChild size="sm" variant="secondary">
          <Link href="/dashboard/billing">Manage Billing</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
