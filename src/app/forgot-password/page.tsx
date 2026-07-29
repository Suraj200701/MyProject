"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { ArrowLeft, Loader2, MailCheck } from "lucide-react";
import Link from "next/link";

import { AuthShell, AuthFooterLink } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ForgotPasswordPage() {
  const [email, setEmail] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [sent, setSent] = React.useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) {
      toast.error("Please enter your email address.");
      return;
    }
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      setSent(true);
      toast.success("Reset link sent.");
    }, 1100);
  }

  return (
    <AuthShell
      title={sent ? "Check your email" : "Forgot your password?"}
      description={
        sent
          ? "We've sent password reset instructions to your inbox."
          : "Enter your email and we'll send you a link to reset your password."
      }
      footer={<AuthFooterLink prompt="Remembered it after all?" href="/login" label="Back to sign in" />}
    >
      <AnimatePresence mode="wait">
        {sent ? (
          <motion.div
            key="success"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col items-center gap-4 py-2 text-center"
          >
            <div className="flex size-14 items-center justify-center rounded-2xl bg-success/15 text-success">
              <MailCheck className="size-7" />
            </div>
            <div>
              <p className="text-sm text-foreground">
                We sent a reset link to <span className="font-medium">{email}</span>
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Didn&apos;t get it? Check your spam folder or try again.
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="default"
              className="mt-2 w-full"
              onClick={() => setSent(false)}
            >
              Use a different email
            </Button>
            <Link
              href="/login"
              className="mt-1 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline underline-offset-4"
            >
              <ArrowLeft className="size-3.5" />
              Back to sign in
            </Link>
          </motion.div>
        ) : (
          <motion.form
            key="form"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            onSubmit={handleSubmit}
            className="flex flex-col gap-5"
          >
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

            <Button type="submit" variant="gradient" size="lg" disabled={loading} className="mt-1 w-full">
              {loading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Sending link...
                </>
              ) : (
                "Send reset link"
              )}
            </Button>
          </motion.form>
        )}
      </AnimatePresence>
    </AuthShell>
  );
}
