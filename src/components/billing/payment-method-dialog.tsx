"use client";

import * as React from "react";
import { toast } from "sonner";
import { CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function PaymentMethodDialog() {
  const [open, setOpen] = React.useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          <CreditCard className="size-3.5" />
          Manage Payment Method
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Payment method</DialogTitle>
          <DialogDescription>
            This is a demo screen — no real card details are collected or stored here.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-2/40 px-4 py-3.5">
          <div className="flex h-8 w-12 items-center justify-center rounded-md bg-surface-2 text-[10px] font-bold text-muted-foreground">
            VISA
          </div>
          <div>
            <p className="text-sm font-medium">•••• •••• •••• 4242</p>
            <p className="text-xs text-muted-foreground">Expires 09/28</p>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          To update your payment method, please contact billing support — card entry is disabled in this preview.
        </p>
        <DialogFooter>
          <Button
            size="sm"
            onClick={() => {
              toast.success("Billing support has been notified");
              setOpen(false);
            }}
          >
            Contact billing support
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
