"use client";

import * as React from "react";
import { toast } from "sonner";
import { Laptop, Smartphone } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";

const SESSIONS = [
  { id: "s1", device: "MacBook Pro · Chrome", location: "Mumbai, India", lastActive: "Active now", icon: Laptop, current: true },
  { id: "s2", device: "iPhone 15 · Safari", location: "Mumbai, India", lastActive: "2 hours ago", icon: Smartphone, current: false },
  { id: "s3", device: "Windows PC · Edge", location: "Pune, India", lastActive: "3 days ago", icon: Laptop, current: false },
];

export function SecuritySection() {
  const [twoFactor, setTwoFactor] = React.useState(true);
  const [sessions, setSessions] = React.useState(SESSIONS);

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label>Current password</Label>
              <Input type="password" placeholder="••••••••" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>New password</Label>
              <Input type="password" placeholder="••••••••" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Confirm new password</Label>
              <Input type="password" placeholder="••••••••" />
            </div>
          </div>
          <Button size="sm" onClick={() => toast.success("Password updated")}>
            Update password
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Two-Factor Authentication</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{twoFactor ? "Enabled" : "Disabled"}</p>
              <p className="text-xs text-muted-foreground">
                {twoFactor ? "Your account is protected with an authenticator app." : "Add an extra layer of security to your account."}
              </p>
            </div>
            <Switch
              checked={twoFactor}
              onCheckedChange={(v) => {
                setTwoFactor(v);
                toast.success(v ? "Two-factor authentication enabled" : "Two-factor authentication disabled");
              }}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active Sessions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {sessions.map((s, i) => (
            <React.Fragment key={s.id}>
              {i > 0 && <Separator />}
              <div className="flex items-center gap-3 py-2.5">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2">
                  <s.icon className="size-4 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {s.device} {s.current && <span className="text-xs text-success">(this device)</span>}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {s.location} · {s.lastActive}
                  </p>
                </div>
                {!s.current && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setSessions((prev) => prev.filter((x) => x.id !== s.id));
                      toast.success("Session revoked");
                    }}
                  >
                    Revoke
                  </Button>
                )}
              </div>
            </React.Fragment>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
