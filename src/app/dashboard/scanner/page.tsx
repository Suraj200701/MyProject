"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ScanLine, Search } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScanStepper } from "@/components/scanner/scan-stepper";
import { BrowserMock } from "@/components/scanner/browser-mock";
import { ScanReportView } from "@/components/scanner/scan-report";
import { RecentScans } from "@/components/scanner/recent-scans";
import {
  EXAMPLE_URLS,
  INITIAL_RECENT_SCANS,
  SCAN_STAGES,
  generateScanReport,
  normalizeUrl,
} from "@/components/scanner/mock-data";
import type { RecentScan, ScanReport, ScanStageState } from "@/components/scanner/types";

type ScanPhase = "idle" | "scanning" | "report";

function delay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

export default function ScannerPage() {
  const [url, setUrl] = React.useState("");
  const [phase, setPhase] = React.useState<ScanPhase>("idle");
  const [stages, setStages] = React.useState<ScanStageState[]>(
    SCAN_STAGES.map((s) => ({ ...s, status: "pending", durationMs: 0 })),
  );
  const [report, setReport] = React.useState<ScanReport | null>(null);
  const [recentScans, setRecentScans] = React.useState<RecentScan[]>(INITIAL_RECENT_SCANS);

  const overallProgress = Math.round(
    (stages.filter((s) => s.status === "done").length / stages.length) * 100,
  );

  async function runScan(rawUrl: string) {
    if (!rawUrl.trim() || phase === "scanning") return;
    const { url: fullUrl } = normalizeUrl(rawUrl);
    setUrl(rawUrl);
    setPhase("scanning");
    setReport(null);

    const freshStages: ScanStageState[] = SCAN_STAGES.map((s) => ({ ...s, status: "pending", durationMs: 0 }));
    setStages(freshStages);

    const scanStart = Date.now();
    const stageDurations: Record<string, number> = {};

    for (let i = 0; i < SCAN_STAGES.length; i++) {
      const stageStart = Date.now();
      setStages((prev) => prev.map((s, idx) => (idx === i ? { ...s, status: "active" } : s)));
      await delay(500 + Math.random() * 500);
      const dur = Date.now() - stageStart;
      stageDurations[SCAN_STAGES[i].id] = dur;
      setStages((prev) => prev.map((s, idx) => (idx === i ? { ...s, status: "done", durationMs: dur } : s)));
    }

    const scanDurationMs = Date.now() - scanStart;
    const generated = generateScanReport(fullUrl, scanDurationMs, stageDurations);
    setReport(generated);
    setRecentScans((prev) => [
      { id: generated.id, domain: generated.domain, confidence: generated.confidence, scannedAt: generated.scannedAt },
      ...prev,
    ].slice(0, 8));
    setPhase("report");
  }

  function reset() {
    setPhase("idle");
    setUrl("");
    setReport(null);
    setStages(SCAN_STAGES.map((s) => ({ ...s, status: "pending", durationMs: 0 })));
  }

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
          disabled={phase === "scanning"}
        />
        <Button size="lg" onClick={() => runScan(url)} disabled={phase === "scanning" || !url.trim()}>
          <ScanLine className="size-4" />
          {phase === "scanning" ? "Scanning…" : "Scan Website"}
        </Button>
      </div>

      {phase === "idle" && (
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLE_URLS.map((example) => (
            <button
              key={example}
              onClick={() => runScan(example)}
              className="rounded-full border border-border bg-surface-2/60 px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
            >
              {example.replace("https://", "")}
            </button>
          ))}
        </div>
      )}

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

            {phase === "scanning" && (
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
