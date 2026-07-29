"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Check, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

interface Tier {
  name: string;
  description: string;
  monthly: number | null;
  annual: number | null;
  cta: string;
  href: string;
  highlighted?: boolean;
  features: string[];
}

const TIERS: Tier[] = [
  {
    name: "Free",
    description: "Try the platform with a limited monthly search allowance.",
    monthly: 0,
    annual: 0,
    cta: "Start for free",
    href: "/signup",
    features: [
      "50 lead searches / month",
      "Basic company profiles",
      "CSV export",
      "Community support",
    ],
  },
  {
    name: "Pro",
    description: "For growing sales teams who need reliable, daily lead flow.",
    monthly: 79,
    annual: 63,
    cta: "Start free trial",
    href: "/signup",
    highlighted: true,
    features: [
      "2,500 lead searches / month",
      "AI Lead Discovery",
      "Website Scanner",
      "CRM-ready exports",
      "Priority email support",
    ],
  },
  {
    name: "Business",
    description: "For revenue teams running multi-channel outbound at scale.",
    monthly: 199,
    annual: 159,
    cta: "Start free trial",
    href: "/signup",
    features: [
      "10,000 lead searches / month",
      "Multi API Search",
      "Lead Intelligence scoring",
      "API Manager access",
      "Team seats & roles",
      "Priority chat support",
    ],
  },
  {
    name: "Enterprise",
    description: "Custom volume, security, and support for large organizations.",
    monthly: null,
    annual: null,
    cta: "Contact sales",
    href: "/signup",
    features: [
      "Unlimited lead searches",
      "Dedicated data pipeline",
      "SSO & advanced security",
      "Custom integrations",
      "Dedicated success manager",
      "SLA-backed uptime",
    ],
  },
];

export function PricingSection() {
  const [annual, setAnnual] = React.useState(true);

  return (
    <section id="pricing" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.5 }}
            className="text-sm font-semibold uppercase tracking-wider text-primary"
          >
            Pricing
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.05 }}
            className="mt-3 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
          >
            Simple pricing that scales with your pipeline
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="mt-4 text-balance text-muted-foreground"
          >
            Start free. Upgrade when your team is ready for more volume and intelligence.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="mt-8 flex items-center justify-center gap-3"
          >
            <span
              className={cn(
                "text-sm font-medium transition-colors",
                !annual ? "text-foreground" : "text-muted-foreground",
              )}
            >
              Monthly
            </span>
            <Switch checked={annual} onCheckedChange={setAnnual} aria-label="Toggle annual billing" />
            <span
              className={cn(
                "flex items-center gap-1.5 text-sm font-medium transition-colors",
                annual ? "text-foreground" : "text-muted-foreground",
              )}
            >
              Annual
              <Badge variant="success" className="px-1.5 py-0 text-[10px]">
                Save 20%
              </Badge>
            </span>
          </motion.div>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-6 lg:grid-cols-4 lg:items-stretch">
          {TIERS.map((tier, i) => {
            const price = annual ? tier.annual : tier.monthly;
            return (
              <motion.div
                key={tier.name}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className={cn(
                  "relative flex flex-col rounded-2xl",
                  tier.highlighted
                    ? "bg-[linear-gradient(135deg,var(--color-primary),var(--color-accent))] p-[1.5px] shadow-[0_24px_60px_-24px_var(--color-primary)]"
                    : "border border-border bg-card p-6",
                )}
              >
                <div
                  className={cn(
                    "flex h-full flex-col",
                    tier.highlighted && "rounded-[calc(1rem-1.5px)] bg-surface p-6",
                  )}
                >
                  {tier.highlighted ? (
                    <Badge variant="primary" className="mb-3 w-fit gap-1 px-2.5">
                      <Sparkles className="h-3 w-3" />
                      Most popular
                    </Badge>
                  ) : (
                    <div className="mb-3 h-[22px]" />
                  )}

                  <h3 className="text-lg font-semibold text-foreground">{tier.name}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{tier.description}</p>

                  <div className="mt-6 flex items-baseline gap-1">
                    {price === null ? (
                      <span className="text-3xl font-semibold tracking-tight text-foreground">
                        Custom
                      </span>
                    ) : (
                      <>
                        <span className="text-4xl font-semibold tracking-tight text-foreground">
                          ${price}
                        </span>
                        <span className="text-sm text-muted-foreground">/mo</span>
                      </>
                    )}
                  </div>
                  {annual && price !== null && price > 0 ? (
                    <p className="mt-1 text-xs text-muted-foreground">Billed annually</p>
                  ) : (
                    <p className="mt-1 text-xs text-transparent">placeholder</p>
                  )}

                  <Button
                    asChild
                    variant={tier.highlighted ? "gradient" : "secondary"}
                    className="mt-6 w-full"
                  >
                    <Link href={tier.href}>{tier.cta}</Link>
                  </Button>

                  <ul className="mt-8 flex flex-1 flex-col gap-3">
                    {tier.features.map((feature) => (
                      <li key={feature} className="flex items-start gap-2.5 text-sm">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                        <span className="text-muted-foreground">{feature}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
