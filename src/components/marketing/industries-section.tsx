"use client";

import { motion } from "framer-motion";
import {
  Factory,
  Zap,
  BoxSelect,
  Cog,
  Network,
  HardHat,
  Bot,
  type LucideIcon,
} from "lucide-react";

interface Industry {
  icon: LucideIcon;
  title: string;
  description: string;
}

const INDUSTRIES: Industry[] = [
  {
    icon: Factory,
    title: "Manufacturers",
    description: "Discover buyers and channel partners across every production vertical.",
  },
  {
    icon: Zap,
    title: "Electrical Dealers",
    description: "Find distributors and retailers actively sourcing electrical components.",
  },
  {
    icon: BoxSelect,
    title: "Panel Builders",
    description: "Target control panel fabricators ready to spec your components.",
  },
  {
    icon: Cog,
    title: "OEM",
    description: "Connect with original equipment manufacturers scaling their supply chain.",
  },
  {
    icon: Network,
    title: "System Integrators",
    description: "Reach integrators assembling multi-vendor industrial solutions.",
  },
  {
    icon: HardHat,
    title: "EPC Companies",
    description: "Surface engineering, procurement, and construction firms mid-project.",
  },
  {
    icon: Bot,
    title: "Industrial Automation",
    description: "Identify automation firms modernizing plants and production lines.",
  },
];

export function IndustriesSection() {
  return (
    <section id="industries" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.5 }}
            className="text-sm font-semibold uppercase tracking-wider text-accent"
          >
            Built for industry
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.05 }}
            className="mt-3 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
          >
            Purpose-built for industrial &amp; B2B supply chains
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="mt-4 text-balance text-muted-foreground"
          >
            LeadMaster AI understands the segments that generic prospecting tools miss.
          </motion.p>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {INDUSTRIES.map((industry, i) => {
            const Icon = industry.icon;
            return (
              <motion.div
                key={industry.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.5, delay: (i % 4) * 0.06 }}
                className="group relative overflow-hidden rounded-xl border border-border bg-surface-2/50 p-6 transition-all duration-300 hover:-translate-y-1 hover:border-border-strong hover:bg-surface-2"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/15 text-accent transition-transform duration-300 group-hover:scale-110">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-[15px] font-semibold text-foreground">
                  {industry.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {industry.description}
                </p>
              </motion.div>
            );
          })}

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.5, delay: 0.24 }}
            className="flex flex-col justify-center rounded-xl border border-dashed border-border-strong bg-transparent p-6"
          >
            <p className="text-[15px] font-semibold text-foreground">Don&apos;t see your niche?</p>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Our search covers every registered business category — try a custom query on
              your free trial.
            </p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
