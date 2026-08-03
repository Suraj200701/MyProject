"use client";

import * as React from "react";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Eye, EyeOff, Loader2 } from "lucide-react";

import { AuthShell, AuthFooterLink } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { errorMessage } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import { useAuth } from "@/lib/auth/auth-context";
import Link from "next/link";

function GoogleIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" {...props}>
      <path
        fill="#4285F4"
        d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.64h6.47a5.54 5.54 0 0 1-2.4 3.63v3h3.88c2.27-2.09 3.57-5.17 3.57-8.82Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.07 7.95-2.91l-3.88-3c-1.08.73-2.46 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.27v3.11A12 12 0 0 0 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.28a7.2 7.2 0 0 1 0-4.56V6.61H1.27a12 12 0 0 0 0 10.78l4-3.11Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.76 0 3.34.6 4.58 1.79l3.44-3.44C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.27 6.61l4 3.11C6.22 6.86 8.87 4.75 12 4.75Z"
      />
    </svg>
  );
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, status } = useAuth();
  const [showPassword, setShowPassword] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [googleLoading, setGoogleLoading] = React.useState(false);
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [rememberMe, setRememberMe] = React.useState(true);

  /** Where to land after signing in — set by the dashboard guard on redirect. */
  const nextPath = searchParams.get("next") || "/dashboard";

  /**
   * Bounce users who are *already* signed in when they land here.
   *
   * The latch stops this from also firing the instant `login()` succeeds, which
   * would race the explicit navigation below and send an unverified user to the
   * dashboard instead of /verify-email.
   */
  const wasAlreadySignedIn = React.useRef<boolean | null>(null);
  React.useEffect(() => {
    if (status === "loading") return;
    if (wasAlreadySignedIn.current === null) {
      wasAlreadySignedIn.current = status === "authenticated";
    }
    if (wasAlreadySignedIn.current && status === "authenticated") {
      router.replace(nextPath);
    }
  }, [status, router, nextPath]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Please enter your email and password.");
      return;
    }
    setLoading(true);
    try {
      const user = await login(email, password, rememberMe);
      toast.success("Welcome back!");
      // The backend issues tokens on a correct password — it does not hold the
      // session pending a second factor — so there is no post-login 2FA gate to
      // route through. Passwordless/OTP sign-in lives at /two-factor and is
      // reached from the link below instead.
      router.replace(user.is_email_verified ? nextPath : "/verify-email");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogle() {
    setGoogleLoading(true);
    // Probe before navigating: this deployment 400s if GOOGLE_CLIENT_ID is
    // unset, and because OAuth needs a top-level document load there is no way
    // to catch that after the fact — the user would land on a JSON error page.
    const { available, reason } = await authApi.isGoogleOAuthAvailable();
    if (!available) {
      setGoogleLoading(false);
      toast.error(reason ?? "Google sign-in isn't available on this server.", {
        description: "Sign in with your email and password instead.",
      });
      return;
    }
    window.location.href = authApi.googleLoginUrl();
  }

  return (
    <AuthShell
      title="Welcome back"
      description="Sign in to your LeadMaster AI workspace."
      footer={<AuthFooterLink prompt="Don't have an account?" href="/signup" label="Sign up" />}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Work email</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@company.com"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link
              href="/forgot-password"
              className="text-xs font-medium text-primary hover:underline underline-offset-4"
            >
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              placeholder="Enter your password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              className="pr-9"
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              tabIndex={-1}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            id="remember"
            checked={rememberMe}
            onCheckedChange={(c) => setRememberMe(c === true)}
            disabled={loading}
          />
          <Label htmlFor="remember" className="font-normal text-muted-foreground">
            Remember me for 30 days
          </Label>
        </div>

        <Button type="submit" variant="gradient" size="lg" disabled={loading} className="mt-1 w-full">
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Signing in...
            </>
          ) : (
            "Sign in"
          )}
        </Button>
      </form>

      <div className="my-6 flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="text-xs text-muted-foreground">or continue with</span>
        <Separator className="flex-1" />
      </div>

      <Button
        type="button"
        variant="outline"
        size="lg"
        className="w-full"
        onClick={handleGoogle}
        disabled={googleLoading}
      >
        {googleLoading ? <Loader2 className="size-4 animate-spin" /> : <GoogleIcon />}
        Continue with Google
      </Button>

      <p className="mt-4 text-center text-sm text-muted-foreground">
        <Link
          href="/two-factor"
          className="font-medium text-primary hover:underline underline-offset-4"
        >
          Sign in with a one-time code
        </Link>
      </p>
    </AuthShell>
  );
}


/**
 * Suspense boundary for `useSearchParams()`.
 *
 * Without it, `next build` fails to prerender this route:
 * "useSearchParams() should be wrapped in a suspense boundary".
 */
export default function LoginPage() {
  return (
    <Suspense
      fallback={
    <AuthShell title="Welcome back" description="Sign in to your LeadMaster AI workspace.">
      <div className="flex min-h-[280px] items-center justify-center">
        <Loader2 className="size-5 animate-spin text-primary" />
      </div>
    </AuthShell>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
