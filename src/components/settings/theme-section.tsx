"use client";

import { Check, Laptop, Moon, Sun } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { id: "dark", label: "Dark", icon: Moon, available: true },
  { id: "light", label: "Light", icon: Sun, available: false },
  { id: "system", label: "System", icon: Laptop, available: false },
];

export function ThemeSection() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Theme</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          LeadMaster AI is currently a premium dark-only experience. Light and system themes are on the roadmap.
        </p>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {OPTIONS.map((opt) => (
          <div
            key={opt.id}
            className={cn(
              "relative rounded-xl border p-4 text-center",
              opt.available ? "border-primary/40 bg-primary/[0.06]" : "border-dashed border-border opacity-60",
            )}
          >
            {opt.available && (
              <span className="absolute right-2 top-2 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Check className="size-3" />
              </span>
            )}
            <opt.icon className="mx-auto size-6 text-foreground/80" />
            <p className="mt-2 text-sm font-medium">{opt.label}</p>
            {!opt.available && <p className="mt-0.5 text-[11px] text-muted-foreground">Coming soon</p>}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
