/**
 * How `NEXT_PUBLIC_API_BASE_URL` resolves to a request URL.
 *
 * This is deployment-critical rather than cosmetic. `NEXT_PUBLIC_*` values are
 * inlined when the bundle is built, so a wrong value here cannot be corrected by
 * the running container — it ships to every visitor's browser. The production
 * topology serves the app and the API on one origin, which is expressed as an
 * explicitly empty value, and an earlier `|| "http://localhost:8000"` collapsed
 * that into the dev fallback: every deployed browser would have called port 8000
 * on the visitor's own machine.
 *
 * The module reads the variable at import time, so each case needs a fresh
 * module registry.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

async function loadClient(value: string | undefined) {
  vi.resetModules();
  if (value === undefined) {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", undefined as unknown as string);
  } else {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", value);
  }
  return import("@/lib/api/client");
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("API_ORIGIN", () => {
  it("uses relative URLs when the value is explicitly empty", async () => {
    const { API_ORIGIN, apiUrl } = await loadClient("");

    expect(API_ORIGIN).toBe("");
    // Same-origin: the browser resolves this against whatever host served the
    // page, so one image works on any domain.
    expect(apiUrl("/leads")).toBe("/api/v1/leads");
  });

  it("falls back to the local backend when the variable is not set at all", async () => {
    const { apiUrl } = await loadClient(undefined);

    expect(apiUrl("/leads")).toBe("http://localhost:8000/api/v1/leads");
  });

  it("uses an absolute origin when the API is on another host", async () => {
    const { apiUrl } = await loadClient("https://api.example.com");

    expect(apiUrl("/leads")).toBe("https://api.example.com/api/v1/leads");
  });

  it("strips a trailing slash", async () => {
    const { apiUrl } = await loadClient("https://api.example.com/");

    expect(apiUrl("/leads")).toBe("https://api.example.com/api/v1/leads");
  });

  it("strips an accidental /api/v1 suffix rather than doubling it", async () => {
    const { apiUrl } = await loadClient("https://api.example.com/api/v1");

    expect(apiUrl("/leads")).toBe("https://api.example.com/api/v1/leads");
  });

  it("builds absolute URLs for paths the API returns", async () => {
    const sameOrigin = await loadClient("");
    // `download_url` already carries /api/v1, so it must not be prefixed again.
    expect(sameOrigin.absoluteUrl("/api/v1/exports/abc/download")).toBe(
      "/api/v1/exports/abc/download",
    );

    const remote = await loadClient("https://api.example.com");
    expect(remote.absoluteUrl("/api/v1/exports/abc/download")).toBe(
      "https://api.example.com/api/v1/exports/abc/download",
    );
  });
});
