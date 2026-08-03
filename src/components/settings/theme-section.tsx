"use client";

import * as React from "react";
import { Check, Laptop, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { id: "dark", label: "Dark", icon: Moon },
  { id: "light", label: "Light", icon: Sun },
  { id: "system", label: "System", icon: Laptop },
] as const;

/** No-op subscribe — hydration happens once and never "changes" again. */
const subscribeToNothing = () => () => {};

/**
 * True once hydrated. `useSyncExternalStore` with differing server/client
 * snapshots avoids the `useState` + `useEffect` pattern that React Compiler
 * flags as a cascading render (`react-hooks/set-state-in-effect`).
 */
function useHydrated(): boolean {
  return React.useSyncExternalStore(
    subscribeToNothing,
    () => true,
    () => false,
  );
}

export function ThemeSection() {
  const { theme, setTheme } = useTheme();
  const hydrated = useHydrated();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Theme</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          Choose how LeadMaster AI looks. System follows your operating system setting, and your
          choice is remembered on this device.
        </p>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {OPTIONS.map((option) => {
          // Before hydration the stored theme is unknown; marking nothing
          // selected avoids rendering a checkmark the client then has to move.
          const selected = hydrated && theme === option.id;
          return (
            <button
              key={option.id}
              type="button"
              aria-pressed={selected}
              onClick={() => setTheme(option.id)}
              className={cn(
                "relative rounded-xl border p-4 text-center transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                selected
                  ? "border-primary/40 bg-primary/[0.06]"
                  : "border-border hover:border-border-strong hover:bg-surface-2/60",
              )}
            >
              {selected && (
                <span className="absolute right-2 top-2 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                  <Check className="size-3" />
                </span>
              )}
              <option.icon className="mx-auto size-6 text-foreground/80" />
              <p className="mt-2 text-sm font-medium">{option.label}</p>
            </button>
          );
        })}
      </CardContent>
    </Card>
  );
}
