"use client";

import * as React from "react";
import { toast } from "sonner";
import { Check } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { AsyncContent } from "@/components/shared/async-content";
import { cn } from "@/lib/utils";
import { useCheckout, usePlans, useSubscription } from "@/lib/api/queries";
import { formatMoney } from "@/components/billing/format";
import type { PlanOut } from "@/lib/api/types";

function periodLabel(plan: PlanOut): string {
  return plan.billing_interval === "year" ? "/yr" : "/mo";
}

export function CurrentPlanCard() {
  const [open, setOpen] = React.useState(false);
  const plans = usePlans();
  const subscription = useSubscription();
  const checkout = useCheckout();

  const currentPlan = subscription.data?.plan ?? null;
  const status = subscription.data?.status ?? null;

  const startCheckout = (plan: PlanOut) =>
    checkout.mutate(plan.id, {
      onSuccess: (session) => {
        setOpen(false);
        // Stripe hosts the payment page; the backend returns where to send the
        // user. Nothing is charged inside this app.
        if (session.checkout_url) window.location.assign(session.checkout_url);
        else toast.error("Checkout is unavailable — billing is not configured on this deployment.");
      },
      onError: (error) => toast.error(error.message),
    });

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Current Plan</CardTitle>
        {status ? (
          <Badge variant={status === "active" ? "primary" : "outline"}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </Badge>
        ) : (
          <Skeleton className="h-5 w-16 rounded-full" />
        )}
      </CardHeader>
      <AsyncContent
        isPending={subscription.isPending}
        isError={subscription.isError}
        error={subscription.error}
        className="min-h-[180px] p-5"
      >
        <CardContent>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-semibold">{currentPlan?.name ?? "No plan"}</span>
            <span className="text-muted-foreground">
              {currentPlan
                ? `${formatMoney(currentPlan.price_cents, currentPlan.currency)}${periodLabel(currentPlan)}`
                : ""}
            </span>
          </div>
          <ul className="mt-4 space-y-2">
            {(currentPlan?.features ?? []).map((feature) => (
              <li key={feature} className="flex items-center gap-2 text-sm text-foreground/90">
                <Check className="size-3.5 text-success" />
                {feature}
              </li>
            ))}
          </ul>
          <div className="mt-5 flex gap-2">
            <Button size="sm" onClick={() => setOpen(true)}>
              Upgrade Plan
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => toast("Downgrade requests are reviewed by your account manager")}
            >
              Downgrade
            </Button>
          </div>
        </CardContent>
      </AsyncContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Compare plans</DialogTitle>
          </DialogHeader>
          <AsyncContent
            isPending={plans.isPending}
            isError={plans.isError}
            error={plans.error}
            isEmpty={(plans.data ?? []).length === 0}
            emptyMessage="No plans are configured on this deployment."
            className="min-h-[160px]"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {(plans.data ?? []).map((plan) => {
                const isCurrent = plan.id === currentPlan?.id;
                return (
                  <div
                    key={plan.id}
                    className={cn(
                      "flex flex-col rounded-xl border p-4",
                      isCurrent ? "border-primary/50 bg-primary/[0.06]" : "border-border",
                    )}
                  >
                    {isCurrent && (
                      <Badge variant="primary" className="mb-2 w-fit">
                        Current
                      </Badge>
                    )}
                    <p className="text-sm font-semibold">{plan.name}</p>
                    <p className="mt-1 text-xl font-semibold">
                      {formatMoney(plan.price_cents, plan.currency)}
                      <span className="text-sm font-normal text-muted-foreground">
                        {periodLabel(plan)}
                      </span>
                    </p>
                    <ul className="mt-3 flex-1 space-y-1.5">
                      {plan.features.map((feature) => (
                        <li
                          key={feature}
                          className="flex items-start gap-1.5 text-xs text-muted-foreground"
                        >
                          <Check className="mt-0.5 size-3 shrink-0 text-success" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                    <Button
                      size="sm"
                      variant={isCurrent ? "secondary" : "outline"}
                      className="mt-4"
                      disabled={isCurrent || checkout.isPending}
                      onClick={() => startCheckout(plan)}
                    >
                      {isCurrent ? "Current plan" : "Select"}
                    </Button>
                  </div>
                );
              })}
            </div>
          </AsyncContent>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
