"use client";

import * as React from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function ProfileSection() {
  const [saving, setSaving] = React.useState(false);

  function save() {
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      toast.success("Profile updated");
    }, 600);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-4">
          <Avatar className="size-16 border border-border">
            <AvatarFallback className="bg-[linear-gradient(135deg,var(--color-primary),var(--color-accent))] text-lg text-white">
              SG
            </AvatarFallback>
          </Avatar>
          <Button variant="secondary" size="sm" onClick={() => toast("Avatar upload is not wired up in this demo")}>
            Change avatar
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label>Full name</Label>
            <Input defaultValue="Suraj Gour" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Email</Label>
            <Input defaultValue="suraj.kumar.sharma235@gmail.com" type="email" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Phone</Label>
            <Input defaultValue="+91 98765 43210" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Job title</Label>
            <Input defaultValue="Founder & CEO" />
          </div>
        </div>

        <Button size="sm" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </Button>
      </CardContent>
    </Card>
  );
}
