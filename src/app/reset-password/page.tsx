"use client";

/**
 * Choose a new password from an emailed reset link.
 *
 * The password reset email points here — `/reset-password?token=<jwt>` (see
 * notifications/email_service.py) — and `POST /auth/reset-password` consumes
 * that token exactly once. Without this route the link 404s, which is what a
 * user hits at the end of an otherwise working flow.
 *
 * The token is single-use, so a typo is unrecoverable: the password would be
 * set to something the user can't reproduce, and the same link can't be
 * reopened to correct it. Hence the confirmation field, which the signup form
 * doesn't need — there a typo just means signing in again.
 *
 * Requirements are checked here as well as server-side so the failure arrives
 * before the token is spent, not as a 400 after it's gone.
 */

import * as React from "react";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { CheckCircle2, Eye, EyeOff, KeyRound, Loader2, XCircle } from "lucide-react";

import { AuthShell, AuthFooterLink } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { errorMessage } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";

/** Mirrors `_validate_password_strength` in backend/schemas/user.py. */
function passwordProblem(value: string): string | null {
  if (value.length < 8) return "Password must be at least 8 characters long";
  if (!/[A-Z]/.test(value)) return "Password must contain at least one uppercase letter";
  if (!/\d/.test(value)) return "Password must contain at least one digit";
  return null;
}

function ResetPasswordPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const token = searchParams.get("token");
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [done, setDone] = React.useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;

    const problem = passwordProblem(password);
    if (problem) {
      toast.error(problem);
      return;
    }
    if (password !== confirm) {
      toast.error("Both passwords must match.");
      return;
    }

    setLoading(true);
    try {
      await authApi.resetPassword({ token, new_password: password });
      setDone(true);
      toast.success("Password updated.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  // Arrived without a token — someone opened the URL directly, or the mail
  // client mangled the link. Send them back to request a fresh one.
  if (!token) {
    return (
      <AuthShell
        title="That link looks incomplete"
        description="This page needs the reset link from your email. Request a new one and open it directly from your inbox."
        footer={<AuthFooterLink prompt="Remembered it after all?" href="/login" label="Back to sign in" />}
      >
        <div className="mb-6 flex justify-center">
          <div className="flex size-14 items-center justify-center rounded-2xl bg-destructive/15 text-destructive">
            <XCircle className="size-7" />
          </div>
        </div>
        <Button
          type="button"
          variant="gradient"
          size="lg"
          className="w-full"
          onClick={() => router.push("/forgot-password")}
        >
          Request a new link
        </Button>
      </AuthShell>
    );
  }

  if (done) {
    return (
      <AuthShell
        title="Password updated"
        description="You can now sign in with your new password."
        footer={<AuthFooterLink prompt="Need a different account?" href="/signup" label="Create one" />}
      >
        <div className="mb-6 flex justify-center">
          <div className="flex size-14 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-400">
            <CheckCircle2 className="size-7" />
          </div>
        </div>
        <Button
          type="button"
          variant="gradient"
          size="lg"
          className="w-full"
          onClick={() => router.replace("/login")}
        >
          Continue to sign in
        </Button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Choose a new password"
      description="Pick something you haven't used before. This link works only once."
      footer={<AuthFooterLink prompt="Remembered it after all?" href="/login" label="Back to sign in" />}
    >
      <div className="mb-6 flex justify-center">
        <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/15 text-primary">
          <KeyRound className="size-7" />
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">New password</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              placeholder="Create a password"
              autoComplete="new-password"
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
          <p className="text-xs text-muted-foreground">
            At least 8 characters, with one uppercase letter and one digit.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="confirm">Confirm new password</Label>
          <Input
            id="confirm"
            type={showPassword ? "text" : "password"}
            placeholder="Repeat your password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            disabled={loading}
          />
        </div>

        <Button type="submit" variant="gradient" size="lg" disabled={loading} className="mt-1 w-full">
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Updating...
            </>
          ) : (
            "Update password"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}

/**
 * Suspense boundary for `useSearchParams()`.
 *
 * Without it, `next build` fails to prerender this route:
 * "useSearchParams() should be wrapped in a suspense boundary".
 */
export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <AuthShell title="Choose a new password" description="One moment…">
          <div className="flex min-h-[240px] items-center justify-center">
            <Loader2 className="size-5 animate-spin text-primary" />
          </div>
        </AuthShell>
      }
    >
      <ResetPasswordPageContent />
    </Suspense>
  );
}
