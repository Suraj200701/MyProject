"use client";

/**
 * Client-side route guard for /dashboard/*.
 *
 * Client-side rather than middleware because the session token lives in
 * `localStorage` (see `lib/api/tokens.ts`) — Next.js middleware runs on the edge
 * and can only read cookies, so it cannot see this session. If the backend is
 * ever changed to set an httpOnly refresh cookie, this should move to middleware
 * so unauthenticated users never download the dashboard bundle at all.
 *
 * While `status` is "loading" it renders a full-height spinner rather than
 * `null`: returning null would flash the empty shell on every hard refresh,
 * because the token is in storage but the user hasn't been fetched yet.
 */

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/lib/auth/auth-context";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  React.useEffect(() => {
    if (status !== "unauthenticated") return;
    // Preserve where the user was headed so login can return them there.
    const next = pathname && pathname !== "/dashboard" ? `?next=${encodeURIComponent(pathname)}` : "";
    router.replace(`/login${next}`);
  }, [status, router, pathname]);

  if (status === "authenticated") return <>{children}</>;

  return (
    <div className="flex min-h-[60vh] w-full items-center justify-center" role="status" aria-busy="true">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="size-6 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">
          {status === "unauthenticated" ? "Redirecting to sign in..." : "Loading your workspace..."}
        </p>
      </div>
    </div>
  );
}
