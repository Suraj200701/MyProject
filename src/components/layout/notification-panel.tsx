"use client";

import { Bell, Search, Download, Plug, Sparkles, Info } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { notifications as initialNotifications } from "@/lib/mock-data";
import { cn } from "@/lib/utils";
import * as React from "react";
import type { NotificationItem } from "@/lib/types";

const iconByType: Record<NotificationItem["type"], React.ElementType> = {
  search: Search,
  export: Download,
  api: Plug,
  recommendation: Sparkles,
  system: Info,
};

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const hrs = Math.floor(diff / 3600000);
  if (hrs < 1) return "just now";
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function NotificationPanel() {
  const [items, setItems] = React.useState(initialNotifications);
  const unread = items.filter((n) => !n.read).length;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="size-4.5" />
          {unread > 0 && (
            <span className="absolute right-1.5 top-1.5 flex size-2 rounded-full bg-danger ring-2 ring-background" />
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-96 p-0">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <p className="text-sm font-semibold">Notifications</p>
          <button
            className="text-xs text-primary hover:underline"
            onClick={() => setItems((prev) => prev.map((n) => ({ ...n, read: true })))}
          >
            Mark all read
          </button>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {items.map((n) => {
            const Icon = iconByType[n.type];
            return (
              <div
                key={n.id}
                className={cn(
                  "flex gap-3 px-4 py-3 border-b border-border/60 last:border-0 hover:bg-surface-2/50 transition-colors",
                  !n.read && "bg-primary/[0.04]",
                )}
              >
                <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-2 border border-border">
                  <Icon className="size-4 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium leading-snug">{n.title}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.description}</p>
                  <p className="text-[11px] text-muted-foreground/70 mt-1">{timeAgo(n.createdAt)}</p>
                </div>
                {!n.read && <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />}
              </div>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
