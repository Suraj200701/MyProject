"use client";

import * as React from "react";
import { toast } from "sonner";
import { DatabaseBackup, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";

const SNAPSHOTS = [
  { id: "b1", label: "Daily backup", date: "2026-07-29 03:00", size: "182 MB" },
  { id: "b2", label: "Daily backup", date: "2026-07-28 03:00", size: "180 MB" },
  { id: "b3", label: "Weekly backup", date: "2026-07-22 03:00", size: "176 MB" },
];

export function BackupSection() {
  const [running, setRunning] = React.useState(false);
  const [restoreOpen, setRestoreOpen] = React.useState(false);

  function backupNow() {
    setRunning(true);
    setTimeout(() => {
      setRunning(false);
      toast.success("Backup completed");
    }, 1200);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backup</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-2/40 px-3 py-3">
          <div className="flex size-9 items-center justify-center rounded-lg border border-border bg-surface-2">
            <DatabaseBackup className="size-4 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium">Automatic backups enabled</p>
            <p className="text-xs text-muted-foreground">Last backup: {SNAPSHOTS[0].date}</p>
          </div>
          <Badge variant="success" className="ml-auto">Healthy</Badge>
        </div>

        <div className="flex flex-col gap-1.5 sm:w-64">
          <span className="text-xs text-muted-foreground">Backup frequency</span>
          <Select defaultValue="daily">
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="daily">Daily</SelectItem>
              <SelectItem value="weekly">Weekly</SelectItem>
              <SelectItem value="monthly">Monthly</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex gap-2">
          <Button size="sm" onClick={backupNow} disabled={running}>
            {running && <Loader2 className="size-3.5 animate-spin" />}
            {running ? "Backing up…" : "Backup now"}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setRestoreOpen(true)}>
            Restore from backup
          </Button>
        </div>
      </CardContent>

      <Dialog open={restoreOpen} onOpenChange={setRestoreOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore from backup</DialogTitle>
            <DialogDescription>Choose a snapshot to restore. This will not affect current data in this demo.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            {SNAPSHOTS.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  toast.success(`Restoring from ${s.date}`);
                  setRestoreOpen(false);
                }}
                className="flex w-full items-center justify-between rounded-lg border border-border px-3 py-2.5 text-left transition-colors hover:border-border-strong hover:bg-surface-2/50"
              >
                <div>
                  <p className="text-sm font-medium">{s.label}</p>
                  <p className="text-xs text-muted-foreground">{s.date}</p>
                </div>
                <span className="text-xs text-muted-foreground">{s.size}</span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
