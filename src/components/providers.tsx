"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ApiError } from "@/lib/api/client";
import { AuthProvider } from "@/lib/auth/auth-context";
import { ThemeProvider } from "@/components/theme-provider";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            refetchOnWindowFocus: false,
            /**
             * Retry transient failures only. Retrying a 401/403/404/422 is
             * pointless — the answer will not change — and retrying a 402
             * (out of credits) or 429 (rate limited) actively makes things
             * worse. Network errors and 5xx get two more attempts.
             */
            retry: (failureCount, error) => {
              if (error instanceof ApiError) {
                if (error.status >= 400 && error.status < 500) return false;
              }
              return failureCount < 2;
            },
          },
        },
      }),
  );

  return (
    // ThemeProvider is outermost: it only writes a class to <html> and holds no
    // data, so nothing below it needs to re-render when the theme changes, and
    // components at every depth can read useTheme().
    <ThemeProvider>
      <QueryClientProvider client={client}>
        {/* AuthProvider sits inside QueryClientProvider: it uses useQuery for
            GET /auth/me, and outside the provider that hook would throw. */}
        <AuthProvider>
          <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
