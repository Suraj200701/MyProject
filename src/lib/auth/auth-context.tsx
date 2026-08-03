"use client";

/**
 * Session state for the whole app.
 *
 * Owns three things:
 *   * the current user (fetched once from `GET /auth/me`, then cached)
 *   * the login / signup / OTP / logout transitions
 *   * `status`, which the route guard reads to decide render vs redirect
 *
 * `status` deliberately has a `loading` state distinct from `unauthenticated`.
 * On a hard refresh the token is in localStorage but the user isn't fetched yet;
 * treating that as unauthenticated would bounce a signed-in user to /login on
 * every reload.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { authApi } from "@/lib/api/endpoints";
import { ApiError, setSessionExpiredHandler } from "@/lib/api/client";
import {
  clearTokens,
  getRefreshToken,
  hasSession,
  markSessionBootstrapped,
  setActiveOrganizationId,
  setTokens,
} from "@/lib/api/tokens";
import type { TokenResponse, UserOut } from "@/lib/api/types";
import { readOAuthCallback } from "@/lib/auth/oauth-callback";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: UserOut | null;
  /** Convenience: profile name, falling back to the email local-part. */
  displayName: string;
  initials: string;
  isEmailVerified: boolean;
  login: (email: string, password: string, remember?: boolean) => Promise<UserOut>;
  signup: (input: {
    email: string;
    password: string;
    fullName: string;
    companyName: string;
  }) => Promise<UserOut>;
  verifyOtp: (email: string, code: string) => Promise<UserOut>;
  logout: () => Promise<void>;
  refreshUser: () => void;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

/** Derives initials for the avatar fallback, matching the topbar's existing look. */
function initialsFrom(name: string, email: string): string {
  const source = name.trim() || email.split("@")[0] || "";
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const queryClient = useQueryClient();

  /**
   * Whether a token exists at all. Initialised from storage on mount rather than
   * during render: `localStorage` is unavailable during SSR, and reading it in
   * the initial state would produce a hydration mismatch.
   */
  const [hasToken, setHasToken] = React.useState(false);
  const [bootstrapped, setBootstrapped] = React.useState(false);

  /**
   * Session bootstrap. Runs once, and does two things in a deliberate order.
   *
   * 1. **Consume an OAuth token from the URL first.** The Google callback lands
   *    on `/dashboard?access_token=<JWT>`, so the token has to be persisted
   *    *before* `bootstrapped` flips to true. Otherwise `status` would report
   *    "unauthenticated" for one render, `RequireAuth` would redirect to /login,
   *    and the navigation would discard the very token it was handed. Both
   *    `setTokens` and `setBootstrapped` happening inside this one effect is what
   *    guarantees no render observes the in-between state.
   *
   * 2. Otherwise fall back to whatever is already in storage.
   *
   * The URL is then rewritten to drop the token — see `oauth-callback.ts` for why
   * that matters.
   */
  /**
   * URL to rewrite once the token has been stored.
   *
   * A ref, not state: the pending URL never affects what is rendered, and writing
   * it here keeps the bootstrap effect free of the cascading re-render that
   * `setState`-in-an-effect causes.
   */
  const pendingOAuthCleanup = React.useRef<string | null>(null);

  React.useEffect(() => {
    const callback = readOAuthCallback();
    let sessionExists: boolean;

    if (callback) {
      // Same storage path as email/password login — one mechanism, not two.
      setTokens(callback.accessToken, callback.refreshToken);
      // Deferred to the effect below: calling router.replace during this first
      // mount effect can be dropped by the App Router before hydration settles.
      pendingOAuthCleanup.current = callback.cleanedUrl;
      sessionExists = true;
    } else {
      sessionExists = hasSession();
    }

    /* eslint-disable react-hooks/set-state-in-effect --
       This is the rule's intended "sync from an external system" case, not a
       derived-state mistake. Bootstrap reads `window.location` and
       `localStorage`, neither of which exists during SSR, so these values cannot
       be computed during render without a hydration mismatch. It runs exactly
       once, and both setters are batched into this single pass. */
    setHasToken(sessionExists);
    setBootstrapped(true);
    /* eslint-enable react-hooks/set-state-in-effect */

    // Releases `apiFetch`'s barrier. Must come after the token is persisted, so
    // the first authenticated request already carries it.
    markSessionBootstrapped();
  }, []);

  /**
   * Strips the token from the address bar.
   *
   * `replace`, never `push`: a history entry still containing the JWT would leave
   * it recoverable with the back button.
   *
   * The backend redirects to `/dashboard`, so `cleanedUrl` is normally just
   * `/dashboard`. The `startsWith` check covers a token arriving on some other
   * route (a changed `FRONTEND_URL`, or a manually constructed link) by landing
   * the now-authenticated user on the dashboard rather than leaving them on a
   * page that wasn't meant to receive a session.
   */
  React.useEffect(() => {
    const target = pendingOAuthCleanup.current;
    if (!target) return;
    // Cleared before navigating so a re-run can't replace twice.
    pendingOAuthCleanup.current = null;
    router.replace(target.startsWith("/dashboard") ? target : "/dashboard");
  }, [bootstrapped, router]);

  const userQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    enabled: bootstrapped && hasToken,
    // A 401 here means the token is dead; the client already tried to refresh,
    // so retrying would just repeat a failed request.
    retry: false,
    staleTime: 5 * 60_000,
  });

  /** Wired once so a failed refresh anywhere in the app lands the user on /login. */
  React.useEffect(() => {
    setSessionExpiredHandler(() => {
      setHasToken(false);
      queryClient.clear();
      router.replace("/login");
    });
    return () => setSessionExpiredHandler(null);
  }, [queryClient, router]);

  const applySession = React.useCallback(
    (tokens: TokenResponse) => {
      setTokens(tokens.access_token, tokens.refresh_token);
      setHasToken(true);
      // Seed the cache so the first dashboard render has a user immediately.
      queryClient.setQueryData(["auth", "me"], tokens.user);
      return tokens.user;
    },
    [queryClient],
  );

  const loginMutation = useMutation({
    mutationFn: (input: { email: string; password: string; remember_me?: boolean }) =>
      authApi.login(input),
  });

  const signupMutation = useMutation({
    mutationFn: (input: {
      email: string;
      password: string;
      full_name: string;
      company_name: string;
    }) => authApi.signup(input),
  });

  const otpMutation = useMutation({
    mutationFn: (input: { email: string; code: string }) => authApi.verifyOtp(input),
  });

  const login = React.useCallback(
    async (email: string, password: string, remember = true) => {
      const tokens = await loginMutation.mutateAsync({ email, password, remember_me: remember });
      return applySession(tokens);
    },
    [applySession, loginMutation],
  );

  const signup = React.useCallback(
    async (input: { email: string; password: string; fullName: string; companyName: string }) => {
      const tokens = await signupMutation.mutateAsync({
        email: input.email,
        password: input.password,
        full_name: input.fullName,
        company_name: input.companyName,
      });
      return applySession(tokens);
    },
    [applySession, signupMutation],
  );

  const verifyOtp = React.useCallback(
    async (email: string, code: string) => {
      const tokens = await otpMutation.mutateAsync({ email, code });
      return applySession(tokens);
    },
    [applySession, otpMutation],
  );

  const logout = React.useCallback(async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await authApi.logout(refreshToken);
      } catch {
        // Best effort: if the revoke call fails (offline, token already expired)
        // still clear locally. Leaving the user "logged in" because the server
        // was unreachable is the worse outcome.
      }
    }
    clearTokens();
    setActiveOrganizationId(null);
    setHasToken(false);
    // Drop every cached response so the next account can't see the previous
    // one's leads for a frame.
    queryClient.clear();
    router.replace("/login");
  }, [queryClient, router]);

  const refreshUser = React.useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
  }, [queryClient]);

  const user = userQuery.data ?? null;

  const status: AuthStatus = React.useMemo(() => {
    if (!bootstrapped) return "loading";
    if (!hasToken) return "unauthenticated";
    if (userQuery.isPending) return "loading";
    // A 401 was already handled by the expired-session hook; any other error
    // (backend down) shouldn't be treated as "not logged in", but there's no
    // user to render either, so the guard shows its error state.
    if (userQuery.isError && (userQuery.error as ApiError)?.isUnauthorized) return "unauthenticated";
    return user ? "authenticated" : "loading";
  }, [bootstrapped, hasToken, user, userQuery.error, userQuery.isError, userQuery.isPending]);

  const displayName = user?.profile?.full_name?.trim() || user?.email?.split("@")[0] || "";

  const value = React.useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      displayName,
      initials: initialsFrom(displayName, user?.email ?? ""),
      isEmailVerified: !!user?.is_email_verified,
      login,
      signup,
      verifyOtp,
      logout,
      refreshUser,
    }),
    [status, user, displayName, login, signup, verifyOtp, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside <AuthProvider>. Check src/components/providers.tsx.");
  }
  return context;
}

/** Non-throwing variant, for components that render both signed in and out. */
export function useOptionalAuth(): AuthContextValue | null {
  return React.useContext(AuthContext);
}
