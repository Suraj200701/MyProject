"use client";

import * as React from "react";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { ScanLine, Search, Loader2 } from "lucide-react";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScanStepper } from "@/components/scanner/scan-stepper";
import { BrowserMock } from "@/components/scanner/browser-mock";
import { ScanReportView } from "@/components/scanner/scan-report";
import { RecentScans } from "@/components/scanner/recent-scans";
import { SCAN_STAGES, normalizeUrl, toRecentScan, toScanReport } from "@/components/scanner/scan-adapter";
import type { ScanReport, ScanStageState } from "@/components/scanner/types";
import { ApiError, errorMessage } from "@/lib/api/client";
import { useScanWebsite, useScans } from "@/lib/api/queries";

type ScanPhase = "idle" | "scanning" | "report";

/**
 * Website Scanner, backed by `POST /scan-website`.
 *
 * The scan is a single server-side operation (fetch through the SSRF guard, then
 * extract), so there is no per-stage progress to subscribe to. The stepper still
 * advances while the request is in flight — honest feedback about work genuinely
 * happening — but it no longer *reports* fabricated per-stage timings, and every
 * value in the report now comes from the response rather than from a PRNG seeded
 * on the domain.
 *
 * Recent scans come from `GET /scans` rather than a seeded list.
 */
function ScannerPageContent() {
  const searchParams = useSearchParams();
  const [url, setUrl] = React.useState("");
  const [phase, setPhase] = React.useState<ScanPhase>("idle");
  const [stages, setStages] = React.useState<ScanStageState[]>(
    SCAN_STAGES.map((s) => ({ ...s, status: "pending", durationMs: 0 })),
  );
  const [report, setReport] = React.useState<ScanReport | null>(null);

  const { data: scansPage } = useScans({ page_size: 8 });
  const scanWebsite = useScanWebsite();

  const recentScans = React.useMemo(() => (scansPage?.items ?? []).map(toRecentScan), [scansPage]);

  const overallProgress = Math.round(
    (stages.filter((s) => s.status === "done").length / stages.length) * 100,
  );

  const runScan = React.useCallback(
    async (rawUrl: string) => {
      if (!rawUrl.trim() || scanWebsite.isPending) return;
      const { url: fullUrl } = normalizeUrl(rawUrl);
      setUrl(rawUrl);
      setPhase("scanning");
      setReport(null);
      setStages(SCAN_STAGES.map((s) => ({ ...s, status: "pending", durationMs: 0 })));

      /**
       * Walk the stepper while the request runs.
       *
       * A progress *indicator*, not a measurement: the server does one operation
       * and reports one duration. The interval is cleared the moment the response
       * lands, so the stepper never claims to have finished work that hasn't.
       */
      let cursor = 0;
      const ticker = setInterval(() => {
        setStages((prev) =>
          prev.map((s, i) =>
            i < cursor ? { ...s, status: "done" } : i === cursor ? { ...s, status: "active" } : s,
          ),
        );
        // Hold on the last stage rather than looping back to the first.
        cursor = Math.min(cursor + 1, SCAN_STAGES.length - 1);
      }, 400);

      try {
        const scan = await scanWebsite.mutateAsync(fullUrl);
        clearInterval(ticker);
        setStages((prev) => prev.map((s) => ({ ...s, status: "done" })));
        setReport(toScanReport(scan));
        setPhase("report");

        if (scan.confidence_score === 0) {
          // A persisted "scan failed" row: the site was unreachable. The report
          // shows that truthfully instead of displaying invented findings.
          toast.warning("That site couldn't be reached.", {
            description: "The scan was recorded, but no details could be extracted.",
          });
        }
      } catch (error) {
        clearInterval(ticker);
        setPhase("idle");
        setStages(SCAN_STAGES.map((s) => ({ ...s, status: "pending", durationMs: 0 })));

        if (error instanceof ApiError && error.isPaymentRequired) {
          toast.error(error.message, { description: "Top up your credits to run more scans." });
        } else if (error instanceof ApiError && error.status === 400) {
          // The SSRF guard's message is the useful one (private address, bad
          // scheme, unresolvable host), so surface it verbatim.
          toast.error(error.message);
        } else {
          toast.error(errorMessage(error));
        }
      }
    },
    [scanWebsite],
  );

  /**
   * Accepts `?url=` so the lead profile's "Scan Website" button can pre-fill this
   * page. Fills the input rather than auto-scanning — a scan costs a credit, so
   * it stays an explicit action.
   */
  const prefilled = React.useRef<string | null>(null);
  React.useEffect(() => {
    const incoming = searchParams.get("url");
    if (!incoming || prefilled.current === incoming) return;
    prefilled.current = incoming;
    setUrl(incoming);
  }, [searchParams]);

  function reset() {
    setPhase("idle");
    setUrl("");
    setReport(null);
    setStages(SCAN_STAGES.map((s) => ({ ...s, status: "pending", durationMs: 0 })));
  }

  const scanning = phase === "scanning";

  return (
    <div>
      <PageHeader
        title="Website Scanner"
        description="Extract contact details, business IDs, and social presence from any website in seconds."
      />

      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runScan(url)}
          placeholder="https://company-website.com"
          className="h-11"
          disabled={scanning}
        />
        <Button size="lg" onClick={() => runScan(url)} disabled={scanning || !url.trim()}>
          <ScanLine className="size-4" />
          {scanning ? "Scanning…" : "Scan Website"}
        </Button>
      </div>

      {/* The example-URL chips are gone: they pointed at invented domains
          (acmesupplies.com, nova-retailgroup.com) that don't resolve, so with a
          real scanner every one would fail. Recent scans in the sidebar serve
          the same "try one" purpose with entries that exist. */}

      <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <AnimatePresence mode="wait">
            {phase === "idle" && (
              <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <EmptyState
                  icon={Search}
                  title="Scan any website for business intelligence"
                  description="LeadMaster AI extracts emails, phone numbers, GST/business IDs, social profiles, and website health signals — paste a URL above to get started."
                />
              </motion.div>
            )}

            {scanning && (
              <motion.div
                key="scanning"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="grid grid-cols-1 gap-4 md:grid-cols-2"
              >
                <div className="rounded-xl border border-border bg-card p-5">
                  <ScanStepper stages={stages} overallProgress={overallProgress} />
                </div>
                <BrowserMock url={url} stages={stages} />
              </motion.div>
            )}

            {phase === "report" && report && (
              <motion.div key="report" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <ScanReportView report={report} onReset={reset} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div>
          <RecentScans scans={recentScans} onSelect={(domain) => runScan(domain)} />
        </div>
      </div>
    </div>
  );
}


/**
 * Suspense boundary for `useSearchParams()`.
 *
 * Without it, `next build` fails to prerender this route:
 * "useSearchParams() should be wrapped in a suspense boundary".
 */
export default function ScannerPage() {
  return (
    <Suspense
      fallback={
    <div className="flex min-h-[60vh] items-center justify-center">
      <Loader2 className="size-5 animate-spin text-primary" />
    </div>
      }
    >
      <ScannerPageContent />
    </Suspense>
  );
}
