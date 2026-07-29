"use client";

import * as React from "react";
import { toast } from "sonner";
import { Building2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function OrganizationSection() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center gap-4">
          <div className="flex size-16 items-center justify-center rounded-xl border border-dashed border-border bg-surface-2 text-muted-foreground">
            <Building2 className="size-6" />
          </div>
          <Button variant="secondary" size="sm" onClick={() => toast("Logo upload is not wired up in this demo")}>
            Upload logo
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label>Company name</Label>
            <Input defaultValue="LeadMaster AI" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Website</Label>
            <Input defaultValue="leadmaster.ai" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Industry</Label>
            <Select defaultValue="saas">
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="saas">SaaS</SelectItem>
                <SelectItem value="manufacturing">Manufacturing</SelectItem>
                <SelectItem value="distribution">Distribution</SelectItem>
                <SelectItem value="consulting">Consulting</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Company size</Label>
            <Select defaultValue="11-50">
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="1-10">1–10 employees</SelectItem>
                <SelectItem value="11-50">11–50 employees</SelectItem>
                <SelectItem value="51-200">51–200 employees</SelectItem>
                <SelectItem value="200+">200+ employees</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Timezone</Label>
            <Select defaultValue="ist">
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="ist">India Standard Time (IST)</SelectItem>
                <SelectItem value="utc">UTC</SelectItem>
                <SelectItem value="est">Eastern Time (ET)</SelectItem>
                <SelectItem value="gst">Gulf Standard Time (GST)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Locale</Label>
            <Select defaultValue="en-in">
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="en-in">English (India)</SelectItem>
                <SelectItem value="en-us">English (US)</SelectItem>
                <SelectItem value="en-gb">English (UK)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <Button size="sm" onClick={() => toast.success("Organization updated")}>
          Save changes
        </Button>
      </CardContent>
    </Card>
  );
}
