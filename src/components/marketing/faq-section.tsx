"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

interface FaqItem {
  question: string;
  answer: string;
}

const FAQS: FaqItem[] = [
  {
    question: "What data sources does LeadMaster AI use?",
    answer:
      "We aggregate business registries, public web data, company websites, and dozens of third-party APIs into a single normalized index, refreshed continuously so results stay current.",
  },
  {
    question: "How is this different from a generic lead list provider?",
    answer:
      "Static lists go stale the day you buy them. LeadMaster AI runs live searches and scans, so every result reflects the current state of a business — including signals like recent website changes or hiring activity.",
  },
  {
    question: "Can I integrate LeadMaster AI with my existing CRM?",
    answer:
      "Yes. Exports are formatted for direct import into Salesforce, HubSpot, and Pipedrive, and the API Manager lets you push enriched leads into any system you already use.",
  },
  {
    question: "Is there a limit on how many searches I can run?",
    answer:
      "Each plan includes a monthly search allowance, from 50 on the Free plan up to unlimited on Enterprise. You can see exact limits in the pricing table above.",
  },
  {
    question: "Do you offer a free trial on paid plans?",
    answer:
      "Yes — Pro and Business plans include a 14-day free trial with full feature access, no credit card required to get started.",
  },
  {
    question: "How accurate is the AI lead scoring?",
    answer:
      "Our scoring model combines firmographic fit, buying-intent signals, and enrichment freshness. Customers typically see a 3-5x improvement in reply rates when prioritizing high-scored leads.",
  },
];

function FaqRow({ item, defaultOpen = false }: { item: FaqItem; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(defaultOpen);
  const id = React.useId();

  return (
    <div className="border-b border-border">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-4 py-5 text-left"
      >
        <span className="text-[15px] font-medium text-foreground">{item.question}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-300",
            open && "rotate-180 text-primary",
          )}
        />
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={id}
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <p className="pb-5 text-sm leading-relaxed text-muted-foreground">{item.answer}</p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export function FaqSection() {
  return (
    <section id="faq" className="relative py-24 lg:py-32">
      <div className="mx-auto max-w-3xl px-6 lg:px-8">
        <div className="text-center">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.5 }}
            className="text-sm font-semibold uppercase tracking-wider text-primary"
          >
            FAQ
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.55, delay: 0.05 }}
            className="mt-3 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
          >
            Frequently asked questions
          </motion.h2>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="mt-12 rounded-xl border border-border bg-card px-6"
        >
          {FAQS.map((item, i) => (
            <FaqRow key={item.question} item={item} defaultOpen={i === 0} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
