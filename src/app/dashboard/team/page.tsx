"use client";

import * as React from "react";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { InviteDialog } from "@/components/team/invite-dialog";
import { MembersList } from "@/components/team/members-list";
import { RolesMatrix } from "@/components/team/roles-matrix";
import { SharedItemsCard } from "@/components/team/shared-items-card";
import { PendingInvites } from "@/components/team/pending-invites";
import { relativeTime } from "@/components/team/adapters";
import {
  useLeads,
  useOrganization,
  useSearchHistory,
  useSubscription,
  useTeamMembers,
} from "@/lib/api/queries";
import type { WorkspaceItem } from "@/components/team/types";

/** First letters of a label, for the row avatar. */
function initialsOf(label: string): string {
  const words = label.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  return (words.length >= 2 ? words[0][0] + words[1][0] : words[0].slice(0, 2)).toUpperCase();
}

export default function TeamPage() {
  const organization = useOrganization();
  const subscription = useSubscription();
  const members = useTeamMembers();
  const leads = useLeads({ page_size: 3, sort_by: "created_at", sort_order: "desc" });
  const searches = useSearchHistory({ page_size: 3 });

  const sharedLeads: WorkspaceItem[] = React.useMemo(
    () =>
      (leads.data?.items ?? []).map((lead) => ({
        id: lead.id,
        name: lead.company,
        meta: [lead.provider ?? "Added manually", relativeTime(lead.createdAt)]
          .filter(Boolean)
          .join(" · "),
        initials: initialsOf(lead.company),
      })),
    [leads.data],
  );

  const sharedSearches: WorkspaceItem[] = React.useMemo(
    () =>
      (searches.data?.items ?? []).map((search) => ({
        id: search.id,
        name: search.query,
        meta: [
          search.location,
          `${search.results} result${search.results === 1 ? "" : "s"}`,
          relativeTime(search.createdAt),
        ]
          .filter(Boolean)
          .join(" · "),
        initials: initialsOf(search.query),
      })),
    [searches.data],
  );

  return (
    <div>
      <PageHeader
        title="Team"
        description="Manage workspace members, roles, and shared resources."
        actions={<InviteDialog />}
      />

      <Card className="mb-5">
        <CardContent className="flex flex-wrap items-center gap-6 p-5">
          <div>
            <p className="text-xs text-muted-foreground">Workspace</p>
            {/* Skeletons rather than a placeholder name: showing a workspace
                name that isn't yours, even for a moment, is worse than a gap. */}
            {organization.data ? (
              <p className="text-sm font-semibold">{organization.data.name}</p>
            ) : (
              <Skeleton className="mt-1 h-5 w-40" />
            )}
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Plan</p>
            {subscription.isPending ? (
              <Skeleton className="mt-1 h-5 w-16 rounded-full" />
            ) : (
              <Badge variant="primary">{subscription.data?.plan?.name ?? "Free"}</Badge>
            )}
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Members</p>
            {members.data ? (
              <p className="text-sm font-semibold">{members.data.length}</p>
            ) : (
              <Skeleton className="mt-1 h-5 w-8" />
            )}
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Created</p>
            {organization.data ? (
              <p className="text-sm font-semibold">
                {new Date(organization.data.created_at).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </p>
            ) : (
              <Skeleton className="mt-1 h-5 w-24" />
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <MembersList />
          <RolesMatrix />
        </div>
        <div className="space-y-5">
          <PendingInvites />
          <SharedItemsCard
            title="Recent Leads"
            items={sharedLeads}
            isPending={leads.isPending}
            isError={leads.isError}
            error={leads.error}
            emptyMessage="No leads in this workspace yet."
          />
          <SharedItemsCard
            title="Recent Searches"
            items={sharedSearches}
            isPending={searches.isPending}
            isError={searches.isError}
            error={searches.error}
            emptyMessage="No searches run in this workspace yet."
          />
        </div>
      </div>
    </div>
  );
}
