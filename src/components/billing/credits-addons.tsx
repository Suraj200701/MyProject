"use client";

import { toast } from "sonner";
import { Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AsyncContent } from "@/components/shared/async-content";
import { useCreditPacks, useCreditTopUp } from "@/lib/api/queries";
import { formatMoney } from "@/components/billing/format";

export function CreditsAddons() {
  const packs = useCreditPacks();
  const topUp = useCreditTopUp();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Credits &amp; Add-ons</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          Need more credits this month? Top up any time — checkout is handled by Stripe.
        </p>
      </CardHeader>
      <AsyncContent
        isPending={packs.isPending}
        isError={packs.isError}
        error={packs.error}
        isEmpty={(packs.data ?? []).length === 0}
        emptyMessage="No credit packs are configured on this deployment."
        className="min-h-[140px] p-5"
      >
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {(packs.data ?? []).map((pack) => (
            <div
              key={pack.id}
              className="flex flex-col items-center gap-2 rounded-xl border border-border p-4 text-center"
            >
              <Zap className="size-5 text-primary" />
              <p className="text-sm font-semibold">{pack.credits.toLocaleString()} credits</p>
              <p className="text-lg font-semibold">{formatMoney(pack.amount_cents, pack.currency)}</p>
              <Button
                size="sm"
                variant="secondary"
                className="mt-1 w-full"
                disabled={topUp.isPending}
                onClick={() =>
                  // Only the pack id is sent: the price and credit amount are
                  // resolved server-side, so a tampered client cannot buy
                  // 20,000 credits at the 1,000-credit price.
                  topUp.mutate(
                    { pack_id: pack.id },
                    {
                      onSuccess: (session) => {
                        if (session.checkout_url) window.location.assign(session.checkout_url);
                        else
                          toast.error(
                            "Checkout is unavailable — billing is not configured on this deployment.",
                          );
                      },
                      onError: (error) => toast.error(error.message),
                    },
                  )
                }
              >
                Buy
              </Button>
            </div>
          ))}
        </CardContent>
      </AsyncContent>
    </Card>
  );
}
