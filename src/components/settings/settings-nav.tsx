"use client";

import {
  User,
  Building2,
  KeyRound,
  ShieldCheck,
  Palette,
  Bell,
  DatabaseBackup,
  Plug,
  CreditCard,
  Users2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type SettingsSectionId =
  | "profile"
  | "organization"
  | "api-keys"
  | "security"
  | "theme"
  | "notifications"
  | "backup"
  | "providers"
  | "billing"
  | "team";

interface SettingsNavItem {
  id: SettingsSectionId;
  label: string;
  icon: LucideIcon;
}

export const settingsSections: SettingsNavItem[] = [
  { id: "profile", label: "Profile", icon: User },
  { id: "organization", label: "Organization", icon: Building2 },
  { id: "api-keys", label: "API Keys", icon: KeyRound },
  { id: "security", label: "Security", icon: ShieldCheck },
  { id: "theme", label: "Theme", icon: Palette },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "backup", label: "Backup", icon: DatabaseBackup },
  { id: "providers", label: "Providers", icon: Plug },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "team", label: "Team", icon: Users2 },
];

export function SettingsNav({
  active,
  onChange,
}: {
  active: SettingsSectionId;
  onChange: (id: SettingsSectionId) => void;
}) {
  return (
    <nav className="md:w-52 md:shrink-0">
      <div className="flex gap-1 overflow-x-auto pb-2 md:flex-col md:overflow-visible md:pb-0 md:sticky md:top-6">
        {settingsSections.map((item) => {
          const isActive = active === item.id;
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={cn(
                "group flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors relative whitespace-nowrap",
                isActive
                  ? "bg-surface-2 text-foreground"
                  : "text-muted-foreground hover:bg-surface-2/60 hover:text-foreground",
              )}
            >
              {isActive && (
                <span className="hidden md:block absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
              )}
              <Icon className="size-4 shrink-0" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
