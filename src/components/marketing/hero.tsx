"use client";

import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, MapPin, PlayCircle, Search, Sparkles, Star } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const QUERIES = [
  "Panel Builders in Pune",
  "Electrical Dealers near Mumbai",
  "OEM Manufacturers in Gujarat",
  "System Integrators in Bengaluru",
  "EPC Companies in Chennai",
];

interface ResultRow {
  name: string;
  location: string;
  score: number;
  tag: string;
}

const RESULTS: ResultRow[] = [
  { name: "Vertex Switchgear Pvt. Ltd.", location: "Pune, MH", score: 94, tag: "Panel Builder" },
  { name: "Sunrise Electrical Traders", location: "Mumbai, MH", score: 89, tag: "Dealer" },
  { name: "Apex Automation Systems", location: "Bengaluru, KA", score: 91, tag: "Integrator" },
  { name: "Bharat Controlgear Co.", location: "Ahmedabad, GJ", score: 87, tag: "OEM" },
];

export function Hero() {
  const [queryIndex, setQueryIndex] = React.useState(0);
  const [visibleResults, setVisibleResults] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    const timeouts: ReturnType<typeof setTimeout>[] = [];

    function runCycle() {
      if (cancelled) return;
      RESULTS.forEach((_, i) => {
        timeouts.push(setTimeout(() => setVisibleResults((v) => Math.max(v, i + 1)), 500 + i * 380));
      });
      timeouts.push(
        setTimeout(() => {
          setQueryIndex((q) => (q + 1) % QUERIES.length);
          setVisibleResults(0);
          runCycle();
        }, 3200),
      );
    }

    runCycle();
    return () => {
      cancelled = true;
      timeouts.forEach(clearTimeout);
    };
  }, []);

  return (
    <section className="relative overflow-hidden bg-grid pt-20 pb-24 lg:pt-28 lg:pb-32">
      {/* ambient glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[-10%] h-[560px] w-[900px] -translate-x-1/2 rounded-full opacity-30 blur-[120px]"
        style={{
          background:
            "radial-gradient(closest-side, var(--color-primary), transparent 70%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-[linear-gradient(to_bottom,transparent,var(--color-background))]"
      />

      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto flex max-w-3xl flex-col items-center text-center">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Badge variant="primary" className="mb-6 gap-1.5 px-3 py-1">
              <Sparkles className="h-3 w-3" />
              Now with AI-powered lead discovery
            </Badge>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
            className="text-balance text-4xl font-semibold leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-6xl"
          >
            Find your next best customer,{" "}
            <span className="text-gradient">before your competitors do</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
            className="mt-6 max-w-2xl text-balance text-lg leading-relaxed text-muted-foreground"
          >
            LeadMaster AI searches, scans, and scores millions of businesses in real time —
            turning raw web data into revenue-ready leads for manufacturers, dealers, and
            industrial teams.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="mt-9 flex flex-col items-center gap-3 sm:flex-row"
          >
            <Button asChild size="lg" variant="gradient" className="group">
              <Link href="/signup">
                Start free trial
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="secondary" className="group">
              <a href="#features">
                <PlayCircle className="h-4 w-4" />
                See how it works
              </a>
            </Button>
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.35 }}
            className="mt-5 text-xs text-muted-foreground"
          >
            No credit card required &middot; 14-day free trial &middot; Cancel anytime
          </motion.p>
        </div>

        {/* Product visual */}
        <motion.div
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.35, ease: [0.16, 1, 0.3, 1] }}
          className="relative mx-auto mt-16 max-w-3xl"
        >
          <div className="glass-strong glow-ring rounded-2xl p-2">
            <div className="rounded-xl bg-surface p-5 sm:p-6">
              {/* search bar */}
              <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-2 px-4 py-3.5">
                <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="relative h-5 flex-1 overflow-hidden text-left">
                  <AnimatePresence mode="wait">
                    <motion.span
                      key={queryIndex}
                      initial={{ y: 14, opacity: 0 }}
                      animate={{ y: 0, opacity: 1 }}
                      exit={{ y: -14, opacity: 0 }}
                      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                      className="absolute inset-0 flex items-center text-sm text-foreground"
                    >
                      {QUERIES[queryIndex]}
                    </motion.span>
                  </AnimatePresence>
                </div>
                <span className="hidden shrink-0 items-center gap-1 rounded-md border border-border-strong bg-surface px-2 py-1 text-[11px] font-medium text-muted-foreground sm:flex">
                  <Sparkles className="h-3 w-3 text-primary" />
                  AI Search
                </span>
              </div>

              {/* results */}
              <div className="mt-4 flex flex-col gap-2">
                {RESULTS.map((row, i) => (
                  <AnimatePresence key={`${queryIndex}-${row.name}`}>
                    {i < visibleResults ? (
                      <motion.div
                        initial={{ opacity: 0, y: 10, scale: 0.98 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                        className="flex items-center justify-between rounded-lg border border-border bg-surface-2/60 px-4 py-3 transition-colors hover:border-border-strong"
                      >
                        <div className="flex items-center gap-3 text-left">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/15 text-xs font-semibold text-primary">
                            {row.name.charAt(0)}
                          </div>
                          <div>
                            <p className="text-sm font-medium text-foreground">{row.name}</p>
                            <p className="flex items-center gap-1 text-xs text-muted-foreground">
                              <MapPin className="h-3 w-3" />
                              {row.location}
                              <span className="mx-1 text-border-strong">&middot;</span>
                              {row.tag}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1 rounded-full bg-success/15 px-2 py-1 text-xs font-semibold text-success">
                          <Star className="h-3 w-3 fill-current" />
                          {row.score}
                        </div>
                      </motion.div>
                    ) : null}
                  </AnimatePresence>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
