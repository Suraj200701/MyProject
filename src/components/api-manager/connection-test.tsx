"use client";

import * as React from "react";
import { CheckCircle2, Info, Loader2, PlugZap, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTestProvider } from "@/lib/api/queries";
import { ApiError } from "@/lib/api/client";
import type { ProviderTestResult } from "@/lib/api/types";

/** Keys worth surfacing in the UI, in the order they help most. */
const DETAIL_ORDER = [
  "http_status",
  "exception",
  "response_body",
  "smtp_code",
  "request_url",
  "hint",
  "expires_in_seconds",
  "scope",
  "project_code",
  "token_type",
  "token_length",
  "places_returned",
  "results_returned",
  "model_count",
  "scanner_enabled",
] as const;

const DETAIL_LABELS: Record<string, string> = {
  http_status: "HTTP status",
  exception: "Exception",
  response_body: "Provider response",
  smtp_code: "SMTP code",
  request_url: "Endpoint",
  hint: "Hint",
  expires_in_seconds: "Token expires in",
  scope: "Scope",
  project_code: "Project",
  token_type: "Token type",
  token_length: "Token length",
  places_returned: "Places returned",
  results_returned: "Results returned",
  model_count: "Models available",
  scanner_enabled: "Scanner enabled",
};

function formatValue(key: string, value: unknown): string {
  if (key === "expires_in_seconds" && typeof value === "number") {
    const hours = Math.floor(value / 3600);
    const minutes = Math.round((value % 3600) / 60);
    return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
  }
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

/**
 * Message for a failure of the *request*, as opposed to a failed test.
 *
 * A rejected mutation means we never got a verdict from the provider — no
 * permission, backend unreachable — which is a different thing from the
 * provider saying no, and must not render as "Authentication Failed".
 *
 * Exported so it can be unit-tested directly: asserting it through a rejected
 * mutation would be testing TanStack Query's promise timing, not this mapping.
 */
export function describeTransportError(error: unknown): string | null {
  if (!error) return null;
  if (error instanceof ApiError && error.isForbidden) {
    return "Your role can't test providers. This needs the api_keys.manage permission.";
  }
  if (error instanceof Error) return error.message;
  return "The test request failed.";
}

/**
 * "Test Connection" for one provider.
 *
 * The backend performs a real authentication round-trip (Mappls exchanges an
 * OAuth token, Google/Bing issue one-result queries, OpenAI lists models), so a
 * green result here means a search will authenticate.
 *
 * A failed test arrives as HTTP 200 with `success: false` — the request worked,
 * the provider rejected us. So this branches on `result.success`, never on
 * whether the mutation rejected; a rejection means something else went wrong
 * (no permission, backend unreachable) and gets its own message.
 */
export function ConnectionTest({ providerId }: { providerId: string }) {
  const test = useTestProvider();
  const [result, setResult] = React.useState<ProviderTestResult | null>(null);

  function run() {
    setResult(null);
    test.mutate(providerId, {
      onSuccess: (data) => setResult(data),
      // Errors are rendered from `test.error` below rather than stored twice.
      onError: () => setResult(null),
    });
  }

  const transportError = test.isError ? describeTransportError(test.error) : null;

  const details = result
    ? DETAIL_ORDER.filter((key) => result.details[key] !== undefined && result.details[key] !== null)
    : [];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={run} disabled={test.isPending}>
          {test.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <PlugZap className="size-3.5" />
          )}
          {test.isPending ? "Connecting…" : "Test Connection"}
        </Button>
        {result ? (
          <span
            className={`inline-flex items-center gap-1.5 text-xs font-medium ${
              result.success ? "text-success" : "text-danger"
            }`}
          >
            {result.success ? (
              <>
                <CheckCircle2 className="size-3.5" /> Connected
              </>
            ) : (
              <>
                <XCircle className="size-3.5" /> Authentication Failed
              </>
            )}
            {result.latency_ms > 0 ? (
              <span className="tabular-nums font-normal text-muted-foreground">
                · {result.latency_ms.toLocaleString()} ms
              </span>
            ) : null}
          </span>
        ) : null}
      </div>

      {transportError ? (
        <p className="flex items-start gap-1.5 rounded-lg border border-danger/30 bg-danger/5 p-2.5 text-xs text-danger">
          <XCircle className="mt-0.5 size-3 shrink-0" />
          {transportError}
        </p>
      ) : null}

      {result ? (
        <div
          className={`rounded-lg border p-2.5 ${
            result.success ? "border-success/30 bg-success/5" : "border-danger/30 bg-danger/5"
          }`}
        >
          <p className="text-xs text-foreground/90">{result.message}</p>
          {details.length > 0 ? (
            <dl className="mt-2 space-y-1">
              {details.map((key) => (
                <div key={key} className="flex gap-2 text-[11px]">
                  <dt className="shrink-0 text-muted-foreground">{DETAIL_LABELS[key] ?? key}</dt>
                  <dd className="min-w-0 break-all font-mono text-foreground/80">
                    {formatValue(key, result.details[key])}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>
      ) : null}

      {!result && !transportError && !test.isPending ? (
        <p className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
          <Info className="mt-0.5 size-3 shrink-0" />
          Performs a real authenticated request against the provider using the same credentials a
          search would use. Nothing is written and no leads are consumed.
        </p>
      ) : null}
    </div>
  );
}
