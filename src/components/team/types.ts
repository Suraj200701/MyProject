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

/**
 * A workspace-wide resource summarised in the Team sidebar.
 *
 * Replaces the previous `SharedItem`, which carried a `sharedBy` person the
 * API does not expose — `meta` holds whatever provenance the resource actually
 * has (source provider, location, result count).
 */
export interface WorkspaceItem {
  id: string;
  name: string;
  meta: string;
  initials: string;
}
