"use client";

import * as React from "react";
import { toast } from "sonner";
import { MoreHorizontal } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AsyncContent } from "@/components/shared/async-content";
import { useRemoveMember, useTeamMembers, useUpdateMemberRole } from "@/lib/api/queries";
import { roleValue, toTeamMember } from "@/components/team/adapters";
import type { TeamMember, TeamRole } from "@/components/team/types";

const ROLE_VARIANT: Record<TeamRole, "primary" | "accent" | "default" | "outline"> = {
  Owner: "primary",
  Admin: "accent",
  Member: "default",
  Viewer: "outline",
};

/** Owner is deliberately absent: transferring ownership is not this control. */
const ASSIGNABLE_ROLES: TeamRole[] = ["Admin", "Member", "Viewer"];

function MemberRow({ member }: { member: TeamMember }) {
  const updateRole = useUpdateMemberRole();
  const removeMember = useRemoveMember();
  const busy = updateRole.isPending || removeMember.isPending;

  return (
    <div className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
      <Avatar className="size-9 border border-border">
        <AvatarFallback className="bg-surface-2 text-xs">{member.initials}</AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{member.name}</p>
        <p className="truncate text-xs text-muted-foreground">{member.email}</p>
      </div>
      <Badge variant={ROLE_VARIANT[member.role]}>{member.role}</Badge>
      <span className="hidden w-28 text-xs text-muted-foreground sm:block">
        {member.status === "invited" ? "Invited" : member.lastActive}
      </span>
      {member.role !== "Owner" ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="size-8" disabled={busy}>
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
              Change role
            </DropdownMenuLabel>
            {ASSIGNABLE_ROLES.map((role) => (
              <DropdownMenuItem
                key={role}
                disabled={role === member.role}
                onSelect={() =>
                  updateRole.mutate(
                    { userId: member.id, role: roleValue(role) },
                    {
                      onSuccess: () => toast.success(`${member.name} is now ${role}`),
                      onError: (mutationError) => toast.error(mutationError.message),
                    },
                  )
                }
              >
                {role}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            {/* The server is the source of truth for the members list: the
                mutation hooks invalidate it, so the row disappears because the
                removal succeeded, not because local state was optimistically
                edited. A failed removal now surfaces instead of silently
                dropping the row from the UI. */}
            <DropdownMenuItem
              variant="destructive"
              onSelect={() =>
                removeMember.mutate(member.id, {
                  onSuccess: () => toast.success(`${member.name} removed from workspace`),
                  onError: (mutationError) => toast.error(mutationError.message),
                })
              }
            >
              Remove member
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : (
        <span className="size-8" />
      )}
    </div>
  );
}

export function MembersList() {
  const { data, isPending, isError, error } = useTeamMembers();
  const members = React.useMemo(() => (data ?? []).map(toTeamMember), [data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Members</CardTitle>
      </CardHeader>
      <AsyncContent
        isPending={isPending}
        isError={isError}
        error={error}
        isEmpty={members.length === 0}
        emptyMessage="No members yet — invite someone to get started."
        className="min-h-[120px] p-5"
      >
        <CardContent className="divide-y divide-border/60">
          {members.map((member) => (
            <MemberRow key={member.id} member={member} />
          ))}
        </CardContent>
      </AsyncContent>
    </Card>
  );
}
