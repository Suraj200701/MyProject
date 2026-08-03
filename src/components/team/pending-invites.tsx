"use client";

import * as React from "react";
import { toast } from "sonner";
import { Mail } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useResendInvitation, useRevokeInvitation, useTeamInvitations } from "@/lib/api/queries";
import { toPendingInvite } from "@/components/team/adapters";

export function PendingInvites() {
  const { data, isPending } = useTeamInvitations();
  const resend = useResendInvitation();
  const revoke = useRevokeInvitation();

  const invites = React.useMemo(
    // The API returns the full invitation history; this card is specifically
    // about the ones still awaiting a response.
    () => (data ?? []).filter((invitation) => invitation.status === "pending").map(toPendingInvite),
    [data],
  );

  // Unchanged behaviour: the card is absent rather than empty when there is
  // nothing pending. While loading, "nothing pending" is not yet known, so it
  // stays hidden instead of flashing an empty card.
  if (isPending || invites.length === 0) return null;

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
            <Button
              variant="ghost"
              size="sm"
              disabled={resend.isPending}
              onClick={() =>
                resend.mutate(invite.id, {
                  onSuccess: () => toast.success(`Invite resent to ${invite.email}`),
                  onError: (error) => toast.error(error.message),
                })
              }
            >
              Resend
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={revoke.isPending}
              onClick={() =>
                revoke.mutate(invite.id, {
                  onSuccess: () => toast.success("Invite cancelled"),
                  onError: (error) => toast.error(error.message),
                })
              }
            >
              Cancel
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
