"use client";

/**
 * Email verification.
 *
 * The backend verifies by **signed link**, not by a typed code: the welcome email
 * contains `/verify-email?token=<jwt>` and `POST /auth/verify-email` consumes
 * that token exactly once. There is no six-digit email-verification code —
 * `/auth/otp/*` hardcodes `purpose=login` and is the passwordless *sign-in*
 * flow, which lives at /two-factor.
 *
 * So this page has two states rather than a code entry form:
 *   * arrived from the email link -> verify automatically and report the outcome
 *   * arrived without a token -> explain to check the inbox, and offer a resend
 *
 * The shell, icon and resend affordance are unchanged; only the OTP boxes are
 * gone, because a code field here could never succeed.
 */

import * as React from "react";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { CheckCircle2, Loader2, MailOpen, XCircle } from "lucide-react";

import { AuthShell, AuthFooterLink } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { ApiError, errorMessage } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import { useAuth } from "@/lib/auth/auth-context";

const RESEND_COOLDOWN_SECONDS = 30;

type VerifyState = "awaiting" | "verifying" | "verified" | "failed";

function VerifyEmailPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { status, isEmailVerified, refreshUser } = useAuth();

  const token = searchParams.get("token");
  const [state, setState] = React.useState<VerifyState>(token ? "verifying" : "awaiting");
  const [failureReason, setFailureReason] = React.useState("");
  const [cooldown, setCooldown] = React.useState(0);
  const [resending, setResending] = React.useState(false);

  React.useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  /**
   * Verify once, on mount, when a token is present.
   *
   * The guard matters: the token is single-use, so a double invocation (React
   * strict mode remounts effects in development) would consume it and then
   * report "already used" on the second call.
   */
  const attempted = React.useRef(false);
  React.useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;

    (async () => {
      try {
        await authApi.verifyEmail(token);
        setState("verified");
        // The cached user still says unverified; refetch so the dashboard guard
        // and any "verify your email" banner update.
        refreshUser();
        toast.success("Email verified.");
      } catch (error) {
        setState("failed");
        setFailureReason(errorMessage(error));
      }
    })();
  }, [token, refreshUser]);

  // Already verified and signed in — nothing to do here.
  React.useEffect(() => {
    if (state === "awaiting" && status === "authenticated" && isEmailVerified) {
      router.replace("/dashboard");
    }
  }, [state, status, isEmailVerified, router]);

  async function handleResend() {
    if (cooldown > 0 || resending) return;
    setResending(true);
    try {
      await authApi.resendVerification();
      setCooldown(RESEND_COOLDOWN_SECONDS);
      toast.success("Verification email sent.");
    } catch (error) {
      // Resending requires a session; if there isn't one, say so usefully
      // instead of showing a bare 401.
      if (error instanceof ApiError && error.isUnauthorized) {
        toast.error("Sign in first, then we can resend your verification email.");
      } else {
        toast.error(errorMessage(error));
      }
    } finally {
      setResending(false);
    }
  }

  const copy: Record<VerifyState, { title: string; description: string }> = {
    awaiting: {
      title: "Verify your email",
      description:
        "We've emailed you a verification link. Open it on this device to confirm your address.",
    },
    verifying: { title: "Verifying your email", description: "One moment while we confirm your link." },
    verified: {
      title: "Email verified",
      description: "Your address is confirmed. You're all set.",
    },
    failed: {
      title: "We couldn't verify that link",
      description: failureReason || "The link may have expired or already been used.",
    },
  };

  return (
    <AuthShell
      title={copy[state].title}
      description={copy[state].description}
      footer={<AuthFooterLink prompt="Wrong account?" href="/signup" label="Start over" />}
    >
      <div className="mb-6 flex justify-center">
        <div
          className={
            state === "verified"
              ? "flex size-14 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-400"
              : state === "failed"
                ? "flex size-14 items-center justify-center rounded-2xl bg-destructive/15 text-destructive"
                : "flex size-14 items-center justify-center rounded-2xl bg-primary/15 text-primary"
          }
        >
          {state === "verifying" ? (
            <Loader2 className="size-7 animate-spin" />
          ) : state === "verified" ? (
            <CheckCircle2 className="size-7" />
          ) : state === "failed" ? (
            <XCircle className="size-7" />
          ) : (
            <MailOpen className="size-7" />
          )}
        </div>
      </div>

      <div className="flex flex-col gap-6">
        {state === "verified" ? (
          <Button
            type="button"
            variant="gradient"
            size="lg"
            className="w-full"
            onClick={() => router.replace("/dashboard")}
          >
            Continue to dashboard
          </Button>
        ) : state === "verifying" ? (
          <Button type="button" variant="gradient" size="lg" disabled className="w-full">
            <Loader2 className="size-4 animate-spin" />
            Verifying...
          </Button>
        ) : (
          <Button
            type="button"
            variant="gradient"
            size="lg"
            className="w-full"
            onClick={handleResend}
            disabled={cooldown > 0 || resending}
          >
            {resending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Sending...
              </>
            ) : cooldown > 0 ? (
              `Resend in ${cooldown}s`
            ) : (
              "Resend verification email"
            )}
          </Button>
        )}

        {state !== "verified" && (
          <p className="text-center text-sm text-muted-foreground">
            You can keep using LeadMaster AI while your email is unverified.{" "}
            <button
              type="button"
              onClick={() => router.replace("/dashboard")}
              className="font-medium text-primary hover:underline underline-offset-4"
            >
              Skip for now
            </button>
          </p>
        )}
      </div>
    </AuthShell>
  );
}


/**
 * Suspense boundary for `useSearchParams()`.
 *
 * Without it, `next build` fails to prerender this route:
 * "useSearchParams() should be wrapped in a suspense boundary".
 */
export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
    <AuthShell title="Verify your email" description="One moment…">
      <div className="flex min-h-[240px] items-center justify-center">
        <Loader2 className="size-5 animate-spin text-primary" />
      </div>
    </AuthShell>
      }
    >
      <VerifyEmailPageContent />
    </Suspense>
  );
}
