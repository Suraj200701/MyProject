"use client";

import * as React from "react";
import { toast } from "sonner";
import { Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
} from "@/components/ui/dialog";

interface ApiKey {
  id: string;
  name: string;
  masked: string;
  createdAt: string;
  lastUsed: string;
}

const INITIAL_KEYS: ApiKey[] = [
  { id: "k1", name: "Production", masked: "lm_live_••••••••3f9a", createdAt: "2026-04-12", lastUsed: "2 hours ago" },
  { id: "k2", name: "Staging", masked: "lm_test_••••••••7c21", createdAt: "2026-05-30", lastUsed: "3 days ago" },
];

function randomTail() {
  const chars = "abcdef0123456789";
  return Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
}

export function ApiKeysSection() {
  const [keys, setKeys] = React.useState(INITIAL_KEYS);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [revokeTarget, setRevokeTarget] = React.useState<ApiKey | null>(null);
  const [newKeyName, setNewKeyName] = React.useState("");
  const [generatedKey, setGeneratedKey] = React.useState<string | null>(null);

  function generate() {
    if (!newKeyName.trim()) {
      toast.error("Give your key a name");
      return;
    }
    const full = `lm_live_${randomTail()}${randomTail()}${randomTail()}`;
    setGeneratedKey(full);
    setKeys((prev) => [
      { id: `k-${Date.now()}`, name: newKeyName, masked: `lm_live_••••••••${full.slice(-4)}`, createdAt: "just now", lastUsed: "never" },
      ...prev,
    ]);
  }

  function closeCreate() {
    setCreateOpen(false);
    setNewKeyName("");
    setGeneratedKey(null);
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>API Keys</CardTitle>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="size-3.5" />
          Generate New Key
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {keys.map((key) => (
          <div key={key.id} className="flex items-center gap-3 rounded-lg border border-border bg-surface-2/40 px-3 py-2.5">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
              <KeyRound className="size-3.5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{key.name}</p>
              <p className="font-mono text-xs text-muted-foreground">{key.masked}</p>
            </div>
            <div className="hidden text-right text-xs text-muted-foreground sm:block">
              <p>Created {key.createdAt}</p>
              <p>Last used {key.lastUsed}</p>
            </div>
            <Button variant="ghost" size="icon" onClick={() => setRevokeTarget(key)}>
              <Trash2 className="size-3.5 text-danger" />
            </Button>
          </div>
        ))}
      </CardContent>

      <Dialog open={createOpen} onOpenChange={(v) => (v ? setCreateOpen(true) : closeCreate())}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate new API key</DialogTitle>
            <DialogDescription>This key will only be shown once — copy it somewhere safe.</DialogDescription>
          </DialogHeader>
          {!generatedKey ? (
            <div className="flex flex-col gap-1.5">
              <Label>Key name</Label>
              <Input value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} placeholder="e.g. CI Pipeline" />
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex gap-2">
                <Input readOnly value={generatedKey} className="font-mono text-xs" />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => {
                    navigator.clipboard?.writeText(generatedKey).catch(() => {});
                    toast.success("Copied to clipboard");
                  }}
                >
                  <Copy className="size-3.5" />
                </Button>
              </div>
              <p className="text-xs text-warning">This is the only time this key will be displayed.</p>
            </div>
          )}
          <DialogFooter>
            {!generatedKey ? (
              <Button size="sm" onClick={generate}>
                Generate
              </Button>
            ) : (
              <Button size="sm" onClick={closeCreate}>
                Done
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!revokeTarget} onOpenChange={(v) => !v && setRevokeTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Revoke &ldquo;{revokeTarget?.name}&rdquo;?</DialogTitle>
            <DialogDescription>
              Any integration using this key will immediately lose access. This can&apos;t be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" size="sm" onClick={() => setRevokeTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                setKeys((prev) => prev.filter((k) => k.id !== revokeTarget?.id));
                toast.success(`Revoked "${revokeTarget?.name}"`);
                setRevokeTarget(null);
              }}
            >
              Revoke key
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
