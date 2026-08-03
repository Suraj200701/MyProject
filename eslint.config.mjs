import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Non-source trees that live inside the repo root. Without these, eslint
    // walks the Python virtualenv and the bundled pgAdmin/StackBuilder assets
    // under .devtools — hundreds of megabytes of vendored JavaScript — and
    // dies with "JavaScript heap out of memory" before linting any of our code.
    "backend/venv/**",
    "backend/**/__pycache__/**",
    ".devtools/**",
    "coverage/**",
  ]),
]);

export default eslintConfig;
