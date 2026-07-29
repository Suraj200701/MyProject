"use client";

import * as React from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";

const CATEGORIES = [
  { id: "search", label: "Search Completed", desc: "A search finishes and results are ready" },
  { id: "export", label: "Export Completed", desc: "An export file is ready to download" },
  { id: "api", label: "API Issues", desc: "A provider is degraded or unavailable" },
  { id: "recommendation", label: "Lead Recommendations", desc: "AI surfaces a new high-value lead" },
  { id: "system", label: "System Notifications", desc: "Product updates and account alerts" },
];

type Channel = "email" | "push" | "inApp";
type Prefs = Record<string, Record<Channel, boolean>>;

function defaultPrefs(): Prefs {
  return Object.fromEntries(
    CATEGORIES.map((c) => [c.id, { email: true, push: c.id !== "system", inApp: true }]),
  );
}

export function NotificationsSection() {
  const [prefs, setPrefs] = React.useState<Prefs>(defaultPrefs);

  function toggle(catId: string, channel: Channel) {
    setPrefs((prev) => ({ ...prev, [catId]: { ...prev[catId], [channel]: !prev[catId][channel] } }));
    toast.success("Preferences updated");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notifications</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span />
          <span className="text-center">Email</span>
          <span className="text-center">Push</span>
          <span className="text-center">In-app</span>
        </div>
        <div className="mt-2 divide-y divide-border/60">
          {CATEGORIES.map((cat) => (
            <div key={cat.id} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-x-4 py-3">
              <div>
                <p className="text-sm font-medium">{cat.label}</p>
                <p className="text-xs text-muted-foreground">{cat.desc}</p>
              </div>
              <Switch checked={prefs[cat.id].email} onCheckedChange={() => toggle(cat.id, "email")} />
              <Switch checked={prefs[cat.id].push} onCheckedChange={() => toggle(cat.id, "push")} />
              <Switch checked={prefs[cat.id].inApp} onCheckedChange={() => toggle(cat.id, "inApp")} />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
