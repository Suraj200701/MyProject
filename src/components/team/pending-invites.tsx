"use client";

import * as React from "react";
import { toast } from "sonner";
import { Mail } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PENDING_INVITES } from "@/components/team/mock-data";

export function PendingInvites() {
  const [invites, setInvites] = React.useState(PENDING_INVITES);

  if (invites.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pending Invitations</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {invites.map((invite) => (
          <div key={invite.id} className="flex items-center gap-3 rounded-lg border border-border bg-surface-2/40 px-3 py-2.5">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
              <Mail className="size-3.5 text-muted-foreground" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{invite.email}</p>
              <p className="text-xs text-muted-foreground">
                Sent {invite.sentAt} · <Badge variant="outline" className="ml-0.5">{invite.role}</Badge>
              </p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => toast.success(`Invite resent to ${invite.email}`)}>
              Resend
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setInvites((prev) => prev.filter((i) => i.id !== invite.id));
                toast.success("Invite cancelled");
              }}
            >
              Cancel
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
