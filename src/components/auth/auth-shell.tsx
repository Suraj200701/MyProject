"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Sparkles, ShieldCheck, Zap, TrendingUp } from "lucide-react";

interface AuthShellProps {
  title: string;
  description: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

const highlights = [
  {
    icon: Zap,
    title: "AI-powered enrichment",
    body: "Turn a name and domain into a full buyer profile in seconds.",
  },
  {
    icon: TrendingUp,
    title: "Predictive lead scoring",
    body: "Know exactly which accounts are ready to convert, today.",
  },
  {
    icon: ShieldCheck,
    title: "Enterprise-grade security",
    body: "SOC 2 Type II compliant with SSO and granular access control.",
  },
];

export function AuthShell({ title, description, children, footer }: AuthShellProps) {
  return (
    <div className="relative flex min-h-screen w-full overflow-hidden bg-background">
      {/* Left branding panel */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden border-r border-border bg-surface p-12 lg:flex">
        {/* Gradient mesh / glow background */}
        <div className="pointer-events-none absolute inset-0 bg-grid opacity-40" />
        <div className="pointer-events-none absolute -top-32 -left-32 h-96 w-96 rounded-full bg-[radial-gradient(circle,var(--color-primary)_0%,transparent_70%)] opacity-30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-40 -right-20 h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,var(--color-accent)_0%,transparent_70%)] opacity-25 blur-3xl" />
        <div
          className="pointer-events-none absolute top-1/3 left-1/4 h-64 w-64 rounded-full border border-primary/20 animate-glow-pulse"
          style={{ animationDelay: "0.5s" }}
        />
        <div className="pointer-events-none absolute bottom-1/4 right-1/3 h-40 w-40 rotate-12 rounded-2xl border border-accent/20" />

        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 flex items-center gap-2.5"
        >
          <div className="flex size-9 items-center justify-center rounded-lg bg-[linear-gradient(120deg,var(--color-primary),var(--color-accent))] shadow-[0_0_24px_-4px_var(--color-primary)]">
            <Sparkles className="size-4.5 text-white" />
          </div>
          <span className="text-lg font-semibold tracking-tight text-foreground">
            LeadMaster <span className="text-gradient">AI</span>
          </span>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 max-w-md"
        >
          <h1 className="text-3xl font-semibold leading-tight tracking-tight text-foreground">
            Find your next best customer{" "}
            <span className="text-gradient">before your competitors do.</span>
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">
            LeadMaster AI unifies signal, enrichment, and outreach into one
            intelligence layer built for modern revenue teams.
          </p>

          <div className="mt-10 flex flex-col gap-5">
            {highlights.map((item, i) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.2 + i * 0.08, ease: [0.16, 1, 0.3, 1] }}
                className="flex items-start gap-3"
              >
                <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2/60">
                  <item.icon className="size-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">{item.title}</p>
                  <p className="text-sm text-muted-foreground">{item.body}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="relative z-10 text-xs text-muted-foreground"
        >
          Trusted by revenue teams at fast-growing companies worldwide.
        </motion.p>
      </div>

      {/* Right form panel */}
      <div className="relative flex w-full flex-1 items-center justify-center px-6 py-12 sm:px-10 lg:w-1/2">
        <div className="pointer-events-none absolute inset-0 bg-grid opacity-[0.15] lg:hidden" />

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 w-full max-w-sm"
        >
          {/* Mobile brand mark */}
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <div className="flex size-8 items-center justify-center rounded-lg bg-[linear-gradient(120deg,var(--color-primary),var(--color-accent))]">
              <Sparkles className="size-4 text-white" />
            </div>
            <span className="text-base font-semibold tracking-tight text-foreground">
              LeadMaster <span className="text-gradient">AI</span>
            </span>
          </div>

          <div className="glass-strong rounded-2xl p-7 sm:p-8">
            <div className="mb-7">
              <h2 className="text-xl font-semibold tracking-tight text-foreground">{title}</h2>
              <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
            </div>

            {children}
          </div>

          {footer ? <div className="mt-6 text-center text-sm text-muted-foreground">{footer}</div> : null}
        </motion.div>
      </div>
    </div>
  );
}

export function AuthFooterLink({
  prompt,
  href,
  label,
}: {
  prompt: string;
  href: string;
  label: string;
}) {
  return (
    <>
      {prompt}{" "}
      <Link href={href} className="font-medium text-primary hover:underline underline-offset-4">
        {label}
      </Link>
    </>
  );
}
