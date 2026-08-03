import { RequireAuth } from "@/components/auth/require-auth";
import { AppShell } from "@/components/layout/app-shell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    /**
     * `RequireAuth` wraps `AppShell`, not the other way around.
     *
     * `AppShell` renders the topbar and notification panel, which fetch on mount
     * (dashboard stats, unread count). With the guard *inside* the shell, those
     * requests fired before the session had been established — which broke Google
     * OAuth outright: the callback lands on `/dashboard?access_token=…`, the shell
     * mounted and fired unauthenticated requests in the same tick, each 401 hit
     * the refresh path, found no refresh token (the OAuth callback issues only an
     * access token), and cleared the session that had just been stored.
     *
     * Gating the whole shell means nothing authenticated mounts until there is a
     * session to authenticate with.
     */
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
