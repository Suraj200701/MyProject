export type TeamRole = "Owner" | "Admin" | "Member" | "Viewer";
export type MemberStatus = "active" | "invited";

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: TeamRole;
  status: MemberStatus;
  lastActive: string;
  initials: string;
}

export interface PendingInvite {
  id: string;
  email: string;
  role: TeamRole;
  sentAt: string;
}

export interface SharedItem {
  id: string;
  name: string;
  sharedBy: string;
  sharedByInitials: string;
  sharedAt: string;
}
