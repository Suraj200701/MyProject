"use client";

import { Search, Zap, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NotificationPanel } from "@/components/layout/notification-panel";
import { useUiStore } from "@/store/ui-store";
import { dashboardStats } from "@/lib/mock-data";
import Link from "next/link";

export function Topbar({ onMobileMenu }: { onMobileMenu?: () => void }) {
  const { setCommandOpen } = useUiStore();
  const creditsPct = Math.round((dashboardStats.creditsRemaining / dashboardStats.creditsTotal) * 100);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/70 backdrop-blur-xl px-4 md:px-6">
      <Button variant="ghost" size="icon" className="md:hidden" onClick={onMobileMenu}>
        <Menu className="size-4.5" />
      </Button>

      <button
        onClick={() => setCommandOpen(true)}
        className="flex flex-1 max-w-md items-center gap-2 rounded-lg border border-border bg-surface-2/50 px-3 py-1.5 text-sm text-muted-foreground hover:border-border-strong hover:bg-surface-2 transition-colors"
      >
        <Search className="size-3.5" />
        <span className="flex-1 text-left">Search leads, companies, providers…</span>
        <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-border-strong bg-surface px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          Ctrl K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-2">
        <Badge variant="primary" className="hidden sm:inline-flex">
          <Zap className="size-3" />
          {dashboardStats.creditsRemaining.toLocaleString()} credits · {creditsPct}%
        </Badge>

        <NotificationPanel />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="rounded-full ring-offset-background transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <Avatar className="size-8 border border-border">
                <AvatarFallback className="bg-[linear-gradient(135deg,var(--color-primary),var(--color-accent))] text-white">
                  SG
                </AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <p className="font-medium">Suraj Gour</p>
              <p className="text-xs font-normal text-muted-foreground">suraj@leadmaster.ai</p>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard/settings">Profile & Settings</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/billing">Billing</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/team">Team</Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/login">Sign out</Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
