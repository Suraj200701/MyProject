"use client";

import { motion } from "framer-motion";
import {
  Search,
  Sparkles,
  Layers,
  ScanLine,
  Download,
  Database,
  Plug,
  LineChart,
  type LucideIcon,
} from "lucide-react";

interface Feature {
  icon: LucideIcon;
  title: string;
  description: string;
}

const FEATURES: Feature[] = [
  {
    icon: Search,
    title: "Smart Lead Search",
    description:
      "Query millions of businesses by industry, location, or keyword and get precisely matched leads in seconds.",
  },
  {
    icon: Sparkles,
    title: "AI Lead Discovery",
    description:
      "Let AI surface high-intent prospects you didn't know to look for, ranked by fit and buying signals.",
  },
  {
    icon: Layers,
    title: "Multi API Search",
    description:
      "Blend data from dozens of sources in a single query for coverage no single provider can match.",
  },
  {
    icon: ScanLine,
    title: "Website Scanner",
    description:
      "Automatically scan company websites to extract tech stack, contact details, and buying signals.",
  },
  {
    icon: Download,
    title: "Export Engine",
    description:
      "Push clean, deduplicated lead lists to CSV, Sheets, or straight into your existing workflow.",
  },
  {
    icon: Database,
    title: "CRM Ready",
    description:
      "Native-feel sync patterns for Salesforce, HubSpot, and Pipedrive keep every lead in one system of record.",
  },
  {
    icon: Plug,
    title: "API Manager",
    description:
      "Manage keys, quotas, and integrations for every connected data source from a single control panel.",
  },
  {
    icon: LineChart,
    title: "Lead Intelligence",
    description:
      "Score, segment, and prioritize your pipeline with enrichment data updated in real time.",
  },
];

export function FeaturesSection() {
  return (
    <section id="features" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.5 }}
            className="text-sm font-semibold uppercase tracking-wider text-primary"
          >
            Platform
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.05 }}
            className="mt-3 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
          >
            Everything you need to find and win your next customer
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="mt-4 text-balance text-muted-foreground"
          >
            A single platform that replaces your scraper, your list broker, and your data
            enrichment stack.
          </motion.p>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.5, delay: (i % 4) * 0.06 }}
                className="group relative overflow-hidden rounded-xl border border-border bg-card p-6 transition-all duration-300 hover:-translate-y-1 hover:border-border-strong hover:shadow-[0_16px_40px_-16px_rgba(0,0,0,0.5)]"
              >
                <div
                  aria-hidden
                  className="pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
                  style={{
                    background:
                      "radial-gradient(closest-side, var(--color-primary), transparent 70%)",
                  }}
                />
                <div className="relative flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 text-primary transition-transform duration-300 group-hover:scale-110">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="relative mt-4 text-[15px] font-semibold text-foreground">
                  {feature.title}
                </h3>
                <p className="relative mt-2 text-sm leading-relaxed text-muted-foreground">
                  {feature.description}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
