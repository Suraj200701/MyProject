"use client";

import { useState } from "react";
import { Plus, Zap } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function AddProviderDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [connecting, setConnecting] = useState(false);

  function handleConnect() {
    if (!name.trim() || !key.trim()) {
      toast.error("Enter a provider name and API key to connect.");
      return;
    }
    setConnecting(true);
    window.setTimeout(() => {
      setConnecting(false);
      setOpen(false);
      toast.success(`${name} connected successfully`, {
        description: "New provider is now available in your marketplace.",
      });
      setName("");
      setKey("");
    }, 700);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setName("");
          setKey("");
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="gradient" size="sm">
          <Plus className="size-4" />
          Add Provider
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap className="size-4 text-primary" />
            Connect a new API
          </DialogTitle>
          <DialogDescription>
            Register a provider so LeadMaster AI can start pulling data from it. You can manage
            credentials any time from the provider card.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="provider-name">Provider name</Label>
            <Input
              id="provider-name"
              placeholder="e.g. Clearbit Enrichment"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="provider-key">API key</Label>
            <Input
              id="provider-key"
              type="password"
              placeholder="sk_live_..."
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Keys are encrypted at rest and never leave your workspace.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={handleConnect} disabled={connecting}>
            {connecting ? "Connecting..." : "Connect"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
