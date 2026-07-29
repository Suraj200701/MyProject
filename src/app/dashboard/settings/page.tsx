"use client";

import * as React from "react";
import { PageHeader } from "@/components/shared/page-header";
import { SettingsNav, type SettingsSectionId } from "@/components/settings/settings-nav";
import { ProfileSection } from "@/components/settings/profile-section";
import { OrganizationSection } from "@/components/settings/organization-section";
import { ApiKeysSection } from "@/components/settings/api-keys-section";
import { SecuritySection } from "@/components/settings/security-section";
import { ThemeSection } from "@/components/settings/theme-section";
import { NotificationsSection } from "@/components/settings/notifications-section";
import { BackupSection } from "@/components/settings/backup-section";
import { ProvidersSection } from "@/components/settings/providers-section";
import { BillingLiteSection } from "@/components/settings/billing-lite-section";
import { TeamLiteSection } from "@/components/settings/team-lite-section";

const SECTION_MAP: Record<SettingsSectionId, React.ComponentType> = {
  profile: ProfileSection,
  organization: OrganizationSection,
  "api-keys": ApiKeysSection,
  security: SecuritySection,
  theme: ThemeSection,
  notifications: NotificationsSection,
  backup: BackupSection,
  providers: ProvidersSection,
  billing: BillingLiteSection,
  team: TeamLiteSection,
};

export default function SettingsPage() {
  const [active, setActive] = React.useState<SettingsSectionId>("profile");
  const ActiveSection = SECTION_MAP[active];

  return (
    <div>
      <PageHeader title="Settings" description="Manage your account, workspace, and platform preferences." />
      <div className="flex flex-col gap-6 md:flex-row">
        <SettingsNav active={active} onChange={setActive} />
        <div className="min-w-0 flex-1 animate-fade-in" key={active}>
          <ActiveSection />
        </div>
      </div>
    </div>
  );
}
