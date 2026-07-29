"use client";

import { motion } from "framer-motion";
import { Quote } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";

interface Testimonial {
  quote: string;
  name: string;
  role: string;
  company: string;
  initials: string;
}

const TESTIMONIALS: Testimonial[] = [
  {
    quote:
      "LeadMaster AI replaced three separate tools for us. Our SDRs now spend their time selling instead of building lists by hand.",
    name: "Ananya Rao",
    role: "VP of Sales",
    company: "Voltronix Industrial",
    initials: "AR",
  },
  {
    quote:
      "The Website Scanner alone paid for the subscription in the first month — we found buying signals our old process never surfaced.",
    name: "Marcus Webb",
    role: "Head of Growth",
    company: "GridForge Systems",
    initials: "MW",
  },
  {
    quote:
      "We went from a handful of manual searches a week to thousands of scored, ready-to-call leads every day.",
    name: "Priya Menon",
    role: "Revenue Operations Lead",
    company: "Circuitworks EPC",
    initials: "PM",
  },
  {
    quote:
      "The API Manager made it trivial to plug our own data sources in alongside LeadMaster's — exactly the flexibility enterprise buyers need.",
    name: "David Chen",
    role: "Director of Sales Ops",
    company: "Ferrotech Automation",
    initials: "DC",
  },
];

export function TestimonialsSection() {
  return (
    <section id="testimonials" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.5 }}
            className="text-sm font-semibold uppercase tracking-wider text-primary"
          >
            Loved by revenue teams
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.05 }}
            className="mt-3 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
          >
            Trusted by teams closing enterprise deals
          </motion.h2>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {TESTIMONIALS.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.5, delay: (i % 2) * 0.08 }}
              className="flex flex-col rounded-xl border border-border bg-card p-6 transition-colors duration-300 hover:border-border-strong"
            >
              <Quote className="h-6 w-6 text-primary/50" />
              <p className="mt-4 flex-1 text-[15px] leading-relaxed text-foreground">
                &ldquo;{t.quote}&rdquo;
              </p>
              <div className="mt-6 flex items-center gap-3">
                <Avatar>
                  <AvatarFallback>{t.initials}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="text-sm font-medium text-foreground">{t.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {t.role} &middot; {t.company}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
