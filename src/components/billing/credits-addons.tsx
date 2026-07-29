"use client";

import { toast } from "sonner";
import { Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CREDIT_PACKS } from "@/components/billing/mock-data";

export function CreditsAddons() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Credits &amp; Add-ons</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          Need more credits this month? Top up any time — this is a preview, no real payment is processed.
        </p>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {CREDIT_PACKS.map((pack) => (
          <div key={pack.id} className="flex flex-col items-center gap-2 rounded-xl border border-border p-4 text-center">
            <Zap className="size-5 text-primary" />
            <p className="text-sm font-semibold">{pack.label}</p>
            <p className="text-lg font-semibold">{pack.price}</p>
            <Button
              size="sm"
              variant="secondary"
              className="mt-1 w-full"
              onClick={() => toast.success(`${pack.label} added to your account`)}
            >
              Buy
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
