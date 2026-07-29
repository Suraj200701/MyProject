import type { PendingInvite, SharedItem, TeamMember } from "@/components/team/types";

export const INITIAL_MEMBERS: TeamMember[] = [
  { id: "m1", name: "Suraj Gour", email: "suraj@leadmaster.ai", role: "Owner", status: "active", lastActive: "Active now", initials: "SG" },
  { id: "m2", name: "Priya Mehta", email: "priya@leadmaster.ai", role: "Admin", status: "active", lastActive: "1 hour ago", initials: "PM" },
  { id: "m3", name: "Arjun Kapoor", email: "arjun@leadmaster.ai", role: "Member", status: "active", lastActive: "3 hours ago", initials: "AK" },
  { id: "m4", name: "Riya Nair", email: "riya@leadmaster.ai", role: "Member", status: "active", lastActive: "Yesterday", initials: "RN" },
  { id: "m5", name: "Divya Verma", email: "divya@leadmaster.ai", role: "Viewer", status: "active", lastActive: "2 days ago", initials: "DV" },
  { id: "m6", name: "Karan Singh", email: "karan@leadmaster.ai", role: "Member", status: "active", lastActive: "4 days ago", initials: "KS" },
  { id: "m7", name: "Meera Iyer", email: "meera@leadmaster.ai", role: "Viewer", status: "invited", lastActive: "—", initials: "MI" },
  { id: "m8", name: "Rohan Shah", email: "rohan@leadmaster.ai", role: "Member", status: "invited", lastActive: "—", initials: "RS" },
];

export const PENDING_INVITES: PendingInvite[] = [
  { id: "inv1", email: "meera@leadmaster.ai", role: "Viewer", sentAt: "2 days ago" },
  { id: "inv2", email: "rohan@leadmaster.ai", role: "Member", sentAt: "5 days ago" },
];

export const SHARED_LEADS: SharedItem[] = [
  { id: "sl1", name: "Apex Switchgear Co.", sharedBy: "Priya Mehta", sharedByInitials: "PM", sharedAt: "1 day ago" },
  { id: "sl2", name: "Vertex Controls Pvt Ltd", sharedBy: "Arjun Kapoor", sharedByInitials: "AK", sharedAt: "3 days ago" },
  { id: "sl3", name: "Nova Power Systems", sharedBy: "Riya Nair", sharedByInitials: "RN", sharedAt: "1 week ago" },
];

export const SHARED_SEARCHES: SharedItem[] = [
  { id: "ss1", name: "Panel Builders in Pune", sharedBy: "Suraj Gour", sharedByInitials: "SG", sharedAt: "2 days ago" },
  { id: "ss2", name: "Electrical Dealers near Mumbai", sharedBy: "Priya Mehta", sharedByInitials: "PM", sharedAt: "4 days ago" },
];

export const ROLE_PERMISSIONS: Record<string, Record<string, boolean>> = {
  Owner: { Search: true, Export: true, "Manage API Keys": true, "Manage Billing": true, "Manage Team": true },
  Admin: { Search: true, Export: true, "Manage API Keys": true, "Manage Billing": false, "Manage Team": true },
  Member: { Search: true, Export: true, "Manage API Keys": false, "Manage Billing": false, "Manage Team": false },
  Viewer: { Search: true, Export: false, "Manage API Keys": false, "Manage Billing": false, "Manage Team": false },
};

export const PERMISSION_KEYS = ["Search", "Export", "Manage API Keys", "Manage Billing", "Manage Team"];
