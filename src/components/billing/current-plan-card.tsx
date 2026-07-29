"use client";

import * as React from "react";
import { toast } from "sonner";
import { Check } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { PLANS } from "@/components/billing/mock-data";

export function CurrentPlanCard() {
  const [open, setOpen] = React.useState(false);
  const current = PLANS.find((p) => p.id === "pro")!;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Current Plan</CardTitle>
        <Badge variant="primary">Active</Badge>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-1">
          <span className="text-2xl font-semibold">{current.name}</span>
          <span className="text-muted-foreground">
            {current.price}
            {current.period}
          </span>
        </div>
        <ul className="mt-4 space-y-2">
          {current.features.map((f) => (
            <li key={f} className="flex items-center gap-2 text-sm text-foreground/90">
              <Check className="size-3.5 text-success" />
              {f}
            </li>
          ))}
        </ul>
        <div className="mt-5 flex gap-2">
          <Button size="sm" onClick={() => setOpen(true)}>
            Upgrade Plan
          </Button>
          <Button variant="outline" size="sm" onClick={() => toast("Downgrade requests are reviewed by your account manager")}>
            Downgrade
          </Button>
        </div>
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Compare plans</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {PLANS.map((plan) => (
              <div
                key={plan.id}
                className={cn(
                  "flex flex-col rounded-xl border p-4",
                  plan.highlight ? "border-primary/50 bg-primary/[0.06]" : "border-border",
                )}
              >
                {plan.highlight && <Badge variant="primary" className="mb-2 w-fit">Current</Badge>}
                <p className="text-sm font-semibold">{plan.name}</p>
                <p className="mt-1 text-xl font-semibold">
                  {plan.price}
                  <span className="text-sm font-normal text-muted-foreground">{plan.period}</span>
                </p>
                <ul className="mt-3 flex-1 space-y-1.5">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                      <Check className="mt-0.5 size-3 shrink-0 text-success" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Button
                  size="sm"
                  variant={plan.highlight ? "secondary" : "outline"}
                  className="mt-4"
                  disabled={plan.highlight}
                  onClick={() => {
                    toast.success(`Switched to ${plan.name} plan`);
                    setOpen(false);
                  }}
                >
                  {plan.highlight ? "Current plan" : "Select"}
                </Button>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
