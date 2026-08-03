"use client";

import * as React from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const OPTIONS = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
] as const;

/** No-op subscribe — hydration happens once and never "changes" again. */
const subscribeToNothing = () => () => {};

/**
 * True once the component has hydrated on the client.
 *
 * `useSyncExternalStore` with differing server/client snapshots is the
 * supported way to ask this. The usual `useState(false)` + `useEffect(() =>
 * setMounted(true))` does the same thing by triggering a second render, which
 * React Compiler flags (`react-hooks/set-state-in-effect`) because cascading
 * renders from effects are exactly what it is trying to eliminate.
 */
function useHydrated(): boolean {
  return React.useSyncExternalStore(
    subscribeToNothing,
    () => true,
    () => false,
  );
}

/**
 * Light / Dark / System switcher for the topbar.
 *
 * The icon reflects `resolvedTheme` (what you are actually looking at), while
 * the checkmark reflects `theme` (what you chose) — so "System" stays visibly
 * selected while still showing the sun or moon it resolved to.
 *
 * Neither value exists on the server, so the trigger renders a neutral
 * placeholder until mounted. Rendering the real icon during SSR would emit
 * markup that cannot match the client for a visitor whose stored theme differs
 * from the default, which is the classic next-themes hydration mismatch.
 */
export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const mounted = useHydrated();

  const Icon = !mounted ? Monitor : resolvedTheme === "dark" ? Moon : Sun;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Change theme"
          // Invisible rather than absent before mount: removing it would shift
          // the toolbar layout on hydration.
          className={mounted ? undefined : "opacity-0"}
        >
          <Icon className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36">
        {OPTIONS.map(({ value, label, Icon: OptionIcon }) => (
          <DropdownMenuItem
            key={value}
            onSelect={() => setTheme(value)}
            className="gap-2"
            data-active={mounted && theme === value}
          >
            <OptionIcon className="size-4" />
            <span className="flex-1">{label}</span>
            {mounted && theme === value ? (
              <span aria-hidden className="text-primary">
                ✓
              </span>
            ) : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
