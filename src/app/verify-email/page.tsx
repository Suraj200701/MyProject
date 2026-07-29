"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Loader2, MailOpen } from "lucide-react";

import { AuthShell, AuthFooterLink } from "@/components/auth/auth-shell";
import { OtpInput } from "@/components/auth/otp-input";
import { Button } from "@/components/ui/button";

const CODE_LENGTH = 6;
const RESEND_COOLDOWN_SECONDS = 30;

export default function VerifyEmailPage() {
  const router = useRouter();
  const [code, setCode] = React.useState<string[]>(Array(CODE_LENGTH).fill(""));
  const [verifying, setVerifying] = React.useState(false);
  const [cooldown, setCooldown] = React.useState(RESEND_COOLDOWN_SECONDS);

  React.useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  function verifyCode(fullCode: string) {
    if (fullCode.length !== CODE_LENGTH || verifying) return;
    setVerifying(true);
    setTimeout(() => {
      setVerifying(false);
      toast.success("Email verified.");
      router.push("/dashboard");
    }, 1100);
  }

  function handleManualSubmit(e: React.FormEvent) {
    e.preventDefault();
    verifyCode(code.join(""));
  }

  function handleResend() {
    if (cooldown > 0) return;
    setCode(Array(CODE_LENGTH).fill(""));
    setCooldown(RESEND_COOLDOWN_SECONDS);
    toast.success("Verification code resent.");
  }

  const isComplete = code.every((d) => d.length === 1);

  return (
    <AuthShell
      title="Verify your email"
      description="We've sent a 6-digit code to your inbox. Enter it below to continue."
      footer={<AuthFooterLink prompt="Wrong account?" href="/signup" label="Start over" />}
    >
      <div className="mb-6 flex justify-center">
        <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/15 text-primary">
          <MailOpen className="size-7" />
        </div>
      </div>

      <form onSubmit={handleManualSubmit} className="flex flex-col gap-6">
        <OtpInput
          length={CODE_LENGTH}
          value={code}
          onChange={setCode}
          onComplete={verifyCode}
          disabled={verifying}
        />

        <Button
          type="submit"
          variant="gradient"
          size="lg"
          disabled={!isComplete || verifying}
          className="w-full"
        >
          {verifying ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Verifying...
            </>
          ) : (
            "Verify email"
          )}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          Didn&apos;t get a code?{" "}
          {cooldown > 0 ? (
            <span className="text-muted-foreground">Resend in {cooldown}s</span>
          ) : (
            <button
              type="button"
              onClick={handleResend}
              className="font-medium text-primary hover:underline underline-offset-4"
            >
              Resend code
            </button>
          )}
        </p>
      </form>
    </AuthShell>
  );
}
