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
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { INITIAL_MEMBERS } from "@/components/team/mock-data";
import type { TeamRole } from "@/components/team/types";

const ROLE_VARIANT: Record<TeamRole, "primary" | "accent" | "default" | "outline"> = {
  Owner: "primary",
  Admin: "accent",
  Member: "default",
  Viewer: "outline",
};

export function MembersList() {
  const [members, setMembers] = React.useState(INITIAL_MEMBERS);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Members</CardTitle>
      </CardHeader>
      <CardContent className="divide-y divide-border/60">
        {members.map((m) => (
          <div key={m.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
            <Avatar className="size-9 border border-border">
              <AvatarFallback className="bg-surface-2 text-xs">{m.initials}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{m.name}</p>
              <p className="truncate text-xs text-muted-foreground">{m.email}</p>
            </div>
            <Badge variant={ROLE_VARIANT[m.role]}>{m.role}</Badge>
            <span className="hidden w-28 text-xs text-muted-foreground sm:block">
              {m.status === "invited" ? "Invited" : m.lastActive}
            </span>
            {m.role !== "Owner" ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="size-8">
                    <MoreHorizontal className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={() => toast.success(`Role updated for ${m.name}`)}>
                    Change role
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    variant="destructive"
                    onSelect={() => {
                      setMembers((prev) => prev.filter((x) => x.id !== m.id));
                      toast.success(`${m.name} removed from workspace`);
                    }}
                  >
                    Remove member
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <span className="size-8" />
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
