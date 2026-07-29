"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

export function CtaSection() {
  return (
    <section className="relative py-16 lg:py-20">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="relative overflow-hidden rounded-3xl bg-[linear-gradient(120deg,var(--color-primary),var(--color-accent))] px-8 py-16 text-center sm:px-16"
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-grid opacity-20"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-white/20 blur-3xl"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-black/10 blur-3xl"
          />

          <div className="relative flex flex-col items-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15 backdrop-blur">
              <Sparkles className="h-6 w-6 text-white" />
            </span>
            <h2 className="mt-6 max-w-xl text-balance text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Start finding your next best customers today
            </h2>
            <p className="mt-4 max-w-md text-balance text-white/85">
              Join thousands of revenue teams using LeadMaster AI to build pipeline faster,
              with data they can trust.
            </p>
            <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
              <Button
                asChild
                size="lg"
                className="group bg-white text-primary hover:bg-white/90 hover:text-primary"
              >
                <Link href="/signup">
                  Start free trial
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white"
              >
                <Link href="/login">Sign in</Link>
              </Button>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
