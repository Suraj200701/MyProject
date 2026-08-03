"use client";

import { Bell, Search, Download, Plug, Sparkles, Info, Loader2 } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import * as React from "react";
import type { NotificationItem } from "@/lib/types";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from "@/lib/api/queries";

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
  const [open, setOpen] = React.useState(false);

  // The badge polls independently of the list so it stays current without
  // keeping a 20-item query warm on every page.
  const { data: unread = 0 } = useUnreadCount();
  // Only fetch the list once the panel is actually opened.
  const { data, isPending, isError } = useNotifications(open ? { page_size: 20 } : {});
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  const items = data?.items ?? [];

  return (
    <Popover open={open} onOpenChange={setOpen}>
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
            className="text-xs text-primary hover:underline disabled:opacity-50"
            disabled={markAllRead.isPending || unread === 0}
            onClick={() => markAllRead.mutate()}
          >
            {markAllRead.isPending ? "Marking..." : "Mark all read"}
          </button>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {isPending ? (
            <div className="flex items-center justify-center gap-2 px-4 py-10 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" />
              Loading notifications...
            </div>
          ) : isError ? (
            <p className="px-4 py-10 text-center text-sm text-muted-foreground">
              Couldn&apos;t load notifications.
            </p>
          ) : items.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-muted-foreground">
              You&apos;re all caught up.
            </p>
          ) : (
            items.map((n) => {
              const Icon = iconByType[n.type] ?? Info;
              return (
                <button
                  key={n.id}
                  type="button"
                  // Clicking an unread item marks it read server-side; the badge
                  // and list both refetch from the mutation's invalidation.
                  onClick={() => !n.read && markRead.mutate(n.id)}
                  className={cn(
                    "flex w-full gap-3 px-4 py-3 text-left border-b border-border/60 last:border-0 hover:bg-surface-2/50 transition-colors",
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
                </button>
              );
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
