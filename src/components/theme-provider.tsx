"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ThemeProviderProps } from "next-themes";

/**
 * Theme root for the whole app.
 *
 * `attribute="class"` is required by the design system: `globals.css` declares
 * `@custom-variant dark (&:is(.dark *))`, so every `dark:` utility resolves
 * against a `.dark` class on an ancestor — next-themes puts it on `<html>`.
 *
 * next-themes injects a tiny blocking script into `<head>` that applies the
 * stored (or system) theme before first paint, which is what prevents the
 * flash of the wrong theme. That script writes to `<html>` before React
 * hydrates, so `<html>` in `app/layout.tsx` carries `suppressHydrationWarning`
 * — without it React reports the class it did not render as a mismatch.
 *
 * `disableTransitionOnChange` suppresses the CSS transitions declared on
 * borders/backgrounds for the duration of a theme switch; otherwise every
 * surface animates its colour independently and the change looks like a smear
 * rather than a switch.
 */
export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      storageKey="leadmaster-theme"
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
