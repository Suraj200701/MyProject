"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { OtpInput } from "@/components/auth/otp-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const CODE_LENGTH = 6;

export default function TwoFactorPage() {
  const router = useRouter();
  const [code, setCode] = React.useState<string[]>(Array(CODE_LENGTH).fill(""));
  const [useBackupCode, setUseBackupCode] = React.useState(false);
  const [backupCode, setBackupCode] = React.useState("");
  const [verifying, setVerifying] = React.useState(false);

  function completeVerification() {
    if (verifying) return;
    setVerifying(true);
    setTimeout(() => {
      setVerifying(false);
      toast.success("Two-factor authentication verified.");
      router.push("/dashboard");
    }, 1100);
  }

  function handleCodeComplete(fullCode: string) {
    if (fullCode.length !== CODE_LENGTH) return;
    completeVerification();
  }

  function handleBackupSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!backupCode.trim()) {
      toast.error("Enter a backup code to continue.");
      return;
    }
    completeVerification();
  }

  function toggleMode() {
    setUseBackupCode((v) => !v);
    setCode(Array(CODE_LENGTH).fill(""));
    setBackupCode("");
  }

  const isCodeComplete = code.every((d) => d.length === 1);

  return (
    <AuthShell
      title="Two-factor authentication"
      description={
        useBackupCode
          ? "Enter one of your saved backup codes to continue."
          : "Enter the code from your authenticator app."
      }
      footer={
        <Link href="/login" className="font-medium text-primary hover:underline underline-offset-4">
          Back to sign in
        </Link>
      }
    >
      <div className="mb-6 flex justify-center">
        <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/15 text-primary">
          {useBackupCode ? <KeyRound className="size-7" /> : <ShieldCheck className="size-7" />}
        </div>
      </div>

      {useBackupCode ? (
        <form onSubmit={handleBackupSubmit} className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <Label htmlFor="backupCode">Backup code</Label>
            <Input
              id="backupCode"
              type="text"
              placeholder="xxxx-xxxx-xxxx"
              autoComplete="off"
              value={backupCode}
              onChange={(e) => setBackupCode(e.target.value)}
              disabled={verifying}
            />
          </div>

          <Button type="submit" variant="gradient" size="lg" disabled={verifying} className="w-full">
            {verifying ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Verifying...
              </>
            ) : (
              "Verify and continue"
            )}
          </Button>
        </form>
      ) : (
        <div className="flex flex-col gap-6">
          <OtpInput
            length={CODE_LENGTH}
            value={code}
            onChange={setCode}
            onComplete={handleCodeComplete}
            disabled={verifying}
          />

          <Button
            type="button"
            variant="gradient"
            size="lg"
            disabled={!isCodeComplete || verifying}
            className="w-full"
            onClick={() => completeVerification()}
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

      <p className="mt-6 text-center text-sm text-muted-foreground">
        <button
          type="button"
          onClick={toggleMode}
          className="font-medium text-primary hover:underline underline-offset-4"
        >
          {useBackupCode ? "Use authenticator code instead" : "Use backup code instead"}
        </button>
      </p>
    </AuthShell>
  );
}
