import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/**
 * Component tests run under jsdom.
 *
 * `resolve.tsconfigPaths` reuses the `@/*` aliases from tsconfig.json so test
 * imports resolve exactly as production imports do — hand-maintaining a second
 * alias map is how tests end up importing a different module than the app does.
 *
 * Only `src/**` is included: `next build` owns the app, and pointing vitest at
 * the repo root would sweep in the Python virtualenv and .devtools the way
 * eslint once did.
 */
export default defineConfig({
  plugins: [react()],
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: false,
  },
});
