import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// jsdom is shared across tests in a file; without this a previous test's DOM
// leaks into the next one and queries match stale nodes.
afterEach(() => cleanup());
