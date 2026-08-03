"use client";

/**
 * One-time-code sign-in.
 *
 * This page used to be a post-login "2FA gate", but `POST /auth/login` issues
 * tokens on a correct password — it does not hold the session pending a second
 * factor — so a gate here would have been decorative. The backend *does* fully
 * support code-based sign-in (`/auth/otp/request` then `/auth/otp/verify`, which
 * returns the same token pair), so the page keeps its design and becomes that
 * flow: enter your email, receive a code, sign in.
 *
 * The "backup code" toggle is gone for the same reason: there is no backup-code
 * store in the backend, and a field that accepts anything and then signs you in
 * would be worse than not offering it.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2, Mail, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { OtpInput } from "@/components/auth/otp-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { errorMessage } from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import { useAuth } from "@/lib/auth/auth-context";

const CODE_LENGTH = 6;

/** How long before the user may ask for another code, matching the backend's OTP budget. */
const RESEND_COOLDOWN_SECONDS = 30;

export default function TwoFactorPage() {
  const router = useRouter();
  const { verifyOtp } = useAuth();

  const [stage, setStage] = React.useState<"email" | "code">("email");
  const [email, setEmail] = React.useState("");
  const [code, setCode] = React.useState<string[]>(Array(CODE_LENGTH).fill(""));
  const [sending, setSending] = React.useState(false);
  const [verifying, setVerifying] = React.useState(false);
  const [cooldown, setCooldown] = React.useState(0);

  React.useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  async function requestCode(e?: React.FormEvent) {
    e?.preventDefault();
    if (!email.trim()) {
      toast.error("Enter your email to receive a code.");
      return;
    }
    setSending(true);
    try {
      await authApi.requestOtp({ email: email.trim(), purpose: "login" });
      toast.success(`We sent a ${CODE_LENGTH}-digit code to ${email.trim()}.`);
      setStage("code");
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSending(false);
    }
  }

  const submitCode = React.useCallback(
    async (fullCode: string) => {
      if (verifying || fullCode.length !== CODE_LENGTH) return;
      setVerifying(true);
      try {
        const user = await verifyOtp(email.trim(), fullCode);
        toast.success("Signed in.");
        router.replace(user.is_email_verified ? "/dashboard" : "/verify-email");
      } catch (error) {
        toast.error(errorMessage(error));
        // Clear the boxes so the user can retype without deleting six digits.
        setCode(Array(CODE_LENGTH).fill(""));
      } finally {
        setVerifying(false);
      }
    },
    [email, router, verifyOtp, verifying],
  );

  const isCodeComplete = code.every((d) => d.length === 1);

  return (
    <AuthShell
      title={stage === "email" ? "Sign in with a code" : "Enter your code"}
      description={
        stage === "email"
          ? "We'll email you a one-time code — no password needed."
          : `Enter the ${CODE_LENGTH}-digit code we sent to ${email.trim()}.`
      }
      footer={
        <Link href="/login" className="font-medium text-primary hover:underline underline-offset-4">
          Back to sign in
        </Link>
      }
    >
      <div className="mb-6 flex justify-center">
        <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/15 text-primary">
          {stage === "email" ? <Mail className="size-7" /> : <ShieldCheck className="size-7" />}
        </div>
      </div>

      {stage === "email" ? (
        <form onSubmit={requestCode} className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <Label htmlFor="otp-email">Work email</Label>
            <Input
              id="otp-email"
              type="email"
              placeholder="you@company.com"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={sending}
            />
          </div>

          <Button type="submit" variant="gradient" size="lg" disabled={sending} className="w-full">
            {sending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Sending code...
              </>
            ) : (
              "Send me a code"
            )}
          </Button>
        </form>
      ) : (
        <div className="flex flex-col gap-6">
          <OtpInput
            length={CODE_LENGTH}
            value={code}
            onChange={setCode}
            onComplete={submitCode}
            disabled={verifying}
          />

          <Button
            type="button"
            variant="gradient"
            size="lg"
            disabled={!isCodeComplete || verifying}
            className="w-full"
            onClick={() => submitCode(code.join(""))}
          >
            {verifying ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Verifying...
              </>
            ) : (
              "Verify and continue"
            )}
          </Button>
        </div>
      )}

      {stage === "code" && (
        <p className="mt-6 text-center text-sm text-muted-foreground">
          {cooldown > 0 ? (
            <span>Resend available in {cooldown}s</span>
          ) : (
            <button
              type="button"
              onClick={() => requestCode()}
              disabled={sending}
              className="font-medium text-primary hover:underline underline-offset-4 disabled:opacity-60"
            >
              Send a new code
            </button>
          )}
          <span className="mx-2 text-border">·</span>
          <button
            type="button"
            onClick={() => {
              setStage("email");
              setCode(Array(CODE_LENGTH).fill(""));
            }}
            className="font-medium text-primary hover:underline underline-offset-4"
          >
            Use a different email
          </button>
        </p>
      )}
    </AuthShell>
  );
}
