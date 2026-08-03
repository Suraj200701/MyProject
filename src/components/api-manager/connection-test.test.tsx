import * as React from "react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ConnectionTest, describeTransportError } from "./connection-test";
import { ApiError } from "@/lib/api/client";
import type { ProviderTestResult } from "@/lib/api/types";

/**
 * The mutation hook is exercised for real (TanStack Query, its states and its
 * cache invalidation); only the network boundary is replaced. Mocking the hook
 * itself would leave the pending/settled transitions — the whole point of this
 * component — untested.
 */
const testProvider = vi.fn();
vi.mock("@/lib/api/endpoints", () => ({
  searchApi: {
    get testProvider() {
      return testProvider;
    },
  },
}));

const PROVIDER_ID = "11111111-2222-3333-4444-555555555555";

function renderTest() {
  // `retry: false` so a failing mutation settles once instead of backing off
  // three times and blowing the test timeout.
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ConnectionTest providerId={PROVIDER_ID} />
    </QueryClientProvider>,
  );
}

const SUCCESS: ProviderTestResult = {
  provider: "Mappls (MapmyIndia)",
  success: true,
  authenticated: true,
  message: "Authenticated. Token valid for 23h 0m.",
  latency_ms: 1167,
  details: { expires_in_seconds: 82852, scope: "READ", token_length: 36 },
};

const FAILURE: ProviderTestResult = {
  provider: "Mappls (MapmyIndia)",
  success: false,
  authenticated: false,
  message: "Mappls rejected the credentials (401).",
  latency_ms: 885,
  details: {
    http_status: 401,
    response_body: '{"error":"invalid_client","error_description":"Bad client credentials"}',
    exception: "HTTPStatusError: Client error '401 Unauthorized'",
  },
};

beforeEach(() => testProvider.mockReset());
afterEach(() => vi.useRealTimers());

describe("ConnectionTest", () => {
  it("shows the idle button before anything is run", () => {
    renderTest();
    expect(screen.getByRole("button", { name: /test connection/i })).toBeEnabled();
    expect(screen.queryByText(/connected/i)).not.toBeInTheDocument();
  });

  it("shows Connecting… while the request is in flight, then Connected", async () => {
    let resolve!: (value: ProviderTestResult) => void;
    testProvider.mockReturnValue(new Promise<ProviderTestResult>((r) => (resolve = r)));

    renderTest();
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));

    // Pending state: label swaps and the button locks so it can't be double-fired.
    expect(await screen.findByRole("button", { name: /connecting/i })).toBeDisabled();

    resolve(SUCCESS);

    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /test connection/i })).toBeEnabled();
  });

  it("displays the latency and the provider's message on success", async () => {
    testProvider.mockResolvedValue(SUCCESS);
    renderTest();
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));

    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByText(/1,167 ms/)).toBeInTheDocument();
    expect(screen.getByText(SUCCESS.message)).toBeInTheDocument();
    // expires_in_seconds is humanized rather than shown as raw seconds.
    expect(screen.getByText("23h 1m")).toBeInTheDocument();
  });

  /**
   * The critical behaviour: the backend answers HTTP 200 for a failed test, so
   * the mutation *fulfills*. Branching on rejection instead of on `success`
   * would render this as a pass.
   */
  it("renders Authentication Failed for a fulfilled response with success:false", async () => {
    testProvider.mockResolvedValue(FAILURE);
    renderTest();
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));

    expect(await screen.findByText("Authentication Failed")).toBeInTheDocument();
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
    expect(screen.getByText(FAILURE.message)).toBeInTheDocument();
    expect(screen.getByText(/885 ms/)).toBeInTheDocument();
  });

  it("surfaces the provider's own diagnostics on failure", async () => {
    testProvider.mockResolvedValue(FAILURE);
    renderTest();
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));

    await screen.findByText("Authentication Failed");
    expect(screen.getByText("HTTP status")).toBeInTheDocument();
    expect(screen.getByText("401")).toBeInTheDocument();
    expect(screen.getByText(/invalid_client/)).toBeInTheDocument();
    expect(screen.getByText(/HTTPStatusError/)).toBeInTheDocument();
  });

  /**
   * The request-failure branch is asserted against the pure mapping rather than
   * by rejecting the mutation: driving a rejection through TanStack Query makes
   * the assertion depend on when the library attaches its internal catch, which
   * vitest reports as a test error even though the component handles it. The
   * mapping is the actual logic, and this tests it directly.
   */
  describe("describeTransportError", () => {
    it("explains a 403 as a permissions problem, not a failed test", () => {
      expect(describeTransportError(new ApiError(403, "Forbidden"))).toMatch(
        /role can't test providers/i,
      );
    });

    it("passes through other error messages", () => {
      expect(describeTransportError(new ApiError(500, "Server exploded"))).toBe("Server exploded");
      expect(describeTransportError(new Error("network down"))).toBe("network down");
    });

    it("has a fallback for non-Error throwables", () => {
      expect(describeTransportError("just a string")).toBe("The test request failed.");
    });

    it("returns null when there is no error", () => {
      expect(describeTransportError(null)).toBeNull();
      expect(describeTransportError(undefined)).toBeNull();
    });
  });

  it("clears the previous result when re-run", async () => {
    testProvider.mockResolvedValue(FAILURE);
    renderTest();
    const button = screen.getByRole("button", { name: /test connection/i });
    await userEvent.click(button);
    await screen.findByText("Authentication Failed");

    let resolve!: (value: ProviderTestResult) => void;
    testProvider.mockReturnValue(new Promise<ProviderTestResult>((r) => (resolve = r)));
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));

    // Stale verdict must not linger next to a fresh "Connecting…".
    await waitFor(() =>
      expect(screen.queryByText("Authentication Failed")).not.toBeInTheDocument(),
    );
    resolve(SUCCESS);
    expect(await screen.findByText("Connected")).toBeInTheDocument();
  });

  it("omits the latency chip when the server reports 0 ms", async () => {
    testProvider.mockResolvedValue({
      ...FAILURE,
      latency_ms: 0,
      message: "No credentials configured for Mappls.",
      details: { hint: "Set the Client ID and Client secret." },
    });
    renderTest();
    await userEvent.click(screen.getByRole("button", { name: /test connection/i }));

    await screen.findByText("Authentication Failed");
    // "0 ms" would imply an instantaneous round-trip; nothing was sent.
    expect(screen.queryByText(/ms/)).not.toBeInTheDocument();
    expect(screen.getByText("Hint")).toBeInTheDocument();
  });
});
