"use client";

import { motion } from "framer-motion";
import { Search, Sparkles, Globe2, Building2, Users } from "lucide-react";
import { Card } from "@/components/ui/card";

const QUICK_STARTS = [
  {
    icon: Building2,
    title: "Panel Builders in Pune",
    description: "Manufacturing & switchgear companies",
  },
  {
    icon: Globe2,
    title: "Electrical Dealers near Mumbai",
    description: "Distributors and retail dealers",
  },
  {
    icon: Users,
    title: "System Integrators in Singapore",
    description: "Automation & controls integrators",
  },
];

export function SearchIdle({ onQuickStart }: { onQuickStart: (query: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border py-16 px-6 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="flex size-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 mb-5"
      >
        <Search className="size-6 text-primary" />
      </motion.div>
      <p className="text-base font-semibold">Find your next high-quality lead</p>
      <p className="text-sm text-muted-foreground mt-1.5 max-w-md">
        Search across Google Places, IndiaMART, JustDial and more — LeadMaster AI scores and
        enriches every result automatically.
      </p>

      <div className="mt-8 grid w-full max-w-2xl grid-cols-1 sm:grid-cols-3 gap-3">
        {QUICK_STARTS.map((item, i) => (
          <motion.div
            key={item.title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.1 + i * 0.08, ease: "easeOut" }}
          >
            <Card
              className="p-4 text-left cursor-pointer hover:border-primary/40 hover:bg-primary/[0.04] transition-colors h-full"
              onClick={() => onQuickStart(item.title)}
            >
              <div className="flex size-8 items-center justify-center rounded-lg border border-border bg-surface-2 mb-3">
                <item.icon className="size-4 text-foreground/80" />
              </div>
              <p className="text-sm font-medium">{item.title}</p>
              <p className="text-xs text-muted-foreground mt-1">{item.description}</p>
            </Card>
          </motion.div>
        ))}
      </div>

      <div className="mt-6 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Sparkles className="size-3.5 text-accent" />
        Powered by AI lead scoring across 6+ providers
      </div>
    </div>
  );
}
