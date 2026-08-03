/**
 * Adapters from the team API's wire shapes to the props the existing team
 * components already render.
 *
 * The components were written against a local `TeamMember` / `PendingInvite`
 * shape (display-cased role, pre-formatted "3 hours ago"). Rather than
 * restyling every component to the API's shape — which would mean touching
 * markup the UI freeze protects — the translation lives here, in one place.
 */

import type { InvitationOut, MemberOut, RoleNameApi } from "@/lib/api/types";
import type { PendingInvite, TeamMember, TeamRole } from "@/components/team/types";

/**
 * The API models five roles; the UI's role badge models four. `superadmin` is a
 * platform-operator flag rather than a workspace role, and it renders as Owner
 * because that is the closest thing the workspace UI can express — inventing a
 * fifth badge would change the design.
 */
const ROLE_LABEL: Record<RoleNameApi, TeamRole> = {
  owner: "Owner",
  superadmin: "Owner",
  admin: "Admin",
  member: "Member",
  viewer: "Viewer",
};

export function roleLabel(role: RoleNameApi): TeamRole {
  return ROLE_LABEL[role] ?? "Member";
}

/** UI label -> the lowercase value the API expects on writes. */
export function roleValue(label: TeamRole): Exclude<RoleNameApi, "superadmin"> {
  return label.toLowerCase() as Exclude<RoleNameApi, "superadmin">;
}

/** "Suraj Gour" -> "SG"; falls back to the email's first letters. */
export function initialsFor(name: string | null, email: string): string {
  const source = (name || "").trim() || email.split("@")[0]?.replace(/[._-]+/g, " ") || "?";
  const parts = source.split(/\s+/).filter(Boolean);
  const letters = parts.length >= 2 ? [parts[0][0], parts[1][0]] : [source[0], source[1] ?? ""];
  return letters.join("").toUpperCase();
}

/**
 * Coarse relative time. `Intl.RelativeTimeFormat` keeps this locale-aware
 * without pulling in a date library for what is a single label.
 */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";

  const seconds = Math.round((then - Date.now()) / 1000);
  const absolute = Math.abs(seconds);
  if (absolute < 60) return "Active now";

  const format = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, size] of units) {
    if (absolute >= size) return format.format(Math.round(seconds / size), unit);
  }
  return "Active now";
}

export function toTeamMember(member: MemberOut): TeamMember {
  const name = member.name?.trim() || member.email;
  return {
    // `user_id`, not `id`: every member-scoped route (role change, removal) is
    // keyed by the user, and passing the membership row id would 404.
    id: member.user_id,
    name,
    email: member.email,
    role: roleLabel(member.role),
    status: member.status === "invited" ? "invited" : "active",
    lastActive: member.status === "invited" ? "—" : relativeTime(member.last_active),
    initials: initialsFor(member.name, member.email),
  };
}

export function toPendingInvite(invitation: InvitationOut): PendingInvite {
  return {
    id: invitation.id,
    email: invitation.email,
    role: roleLabel(invitation.role),
    sentAt: relativeTime(invitation.created_at),
  };
}
