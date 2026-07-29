import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { InviteDialog } from "@/components/team/invite-dialog";
import { MembersList } from "@/components/team/members-list";
import { RolesMatrix } from "@/components/team/roles-matrix";
import { SharedItemsCard } from "@/components/team/shared-items-card";
import { PendingInvites } from "@/components/team/pending-invites";
import { INITIAL_MEMBERS, SHARED_LEADS, SHARED_SEARCHES } from "@/components/team/mock-data";

export default function TeamPage() {
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
            <p className="text-sm font-semibold">LeadMaster AI Workspace</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Plan</p>
            <Badge variant="primary">Pro</Badge>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Members</p>
            <p className="text-sm font-semibold">{INITIAL_MEMBERS.length}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Created</p>
            <p className="text-sm font-semibold">Mar 14, 2026</p>
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
          <SharedItemsCard title="Shared Leads" items={SHARED_LEADS} />
          <SharedItemsCard title="Shared Searches" items={SHARED_SEARCHES} />
        </div>
      </div>
    </div>
  );
}
