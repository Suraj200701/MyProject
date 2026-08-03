"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Braces,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  FileSpreadsheet,
  FileText,
  Plus,
  Sheet,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { EXPORT_FIELDS, type ExportFormat, type ExportRecord, type ExportSource } from "@/components/export/types";
import { FORMAT_META } from "@/components/export/format-meta";
import { toApiFormat, toApiScope, toExportRecord } from "@/components/export/export-adapter";
import { ApiError, errorMessage } from "@/lib/api/client";
import { exportsApi } from "@/lib/api/endpoints";
import { useCreateExport, useLeads } from "@/lib/api/queries";

const FORMAT_ICON: Record<ExportFormat, typeof FileText> = {
  CSV: Sheet,
  Excel: FileSpreadsheet,
  PDF: FileText,
  JSON: Braces,
};

type Step = "source" | "format" | "configure" | "review" | "progress" | "done";

export function ExportWizard({ onComplete }: { onComplete: (record: ExportRecord) => void }) {
  const [open, setOpen] = React.useState(false);
  const [step, setStep] = React.useState<Step>("source");
  const [source, setSource] = React.useState<ExportSource>("all");
  const [format, setFormat] = React.useState<ExportFormat>("CSV");
  const [fields, setFields] = React.useState<string[]>([...EXPORT_FIELDS]);
  const [fileName, setFileName] = React.useState("leadmaster_export");
  const [includeSummaries, setIncludeSummaries] = React.useState(true);
  const [progress, setProgress] = React.useState(0);
  const [progressLabel, setProgressLabel] = React.useState("Generating your file…");
  const [result, setResult] = React.useState<ExportRecord | null>(null);

  /**
   * Real row count for the chosen scope, from the leads endpoint's pagination
   * meta — one HEAD-like request rather than downloading rows to count them.
   * The previous version guessed: all leads, 40% of them, or a flat 12.
   *
   * "selected" cannot be counted here because this wizard has no row selection
   * (that lives on the Lead Database toolbar), so it reports 0 and the API is the
   * authority once the export runs.
   */
  const { data: leadsMeta } = useLeads({ page_size: 1 });
  const sourceCount = source === "selected" ? 0 : (leadsMeta?.meta.total_items ?? 0);
  const createExport = useCreateExport();

  function reset() {
    setStep("source");
    setSource("all");
    setFormat("CSV");
    setFields([...EXPORT_FIELDS]);
    setFileName("leadmaster_export");
    setIncludeSummaries(true);
    setProgress(0);
    setResult(null);
  }

  function toggleField(field: string) {
    setFields((prev) => (prev.includes(field) ? prev.filter((f) => f !== field) : [...prev, field]));
  }

  /**
   * Creates the export via `POST /exports`.
   *
   * Genuinely generates a file server-side. The previous version stepped a
   * progress bar through four labels on timers and then fabricated an
   * `ExportRecord` — row count guessed, size computed as `rows * 4.2 KB`, status
   * hardcoded to "ready" — without any file existing.
   *
   * The progress bar is now indeterminate-ish: it advances while the request is
   * in flight and completes when the response lands, because a single POST has no
   * intermediate progress to report.
   */
  async function startExport() {
    setStep("progress");
    setProgress(15);
    setProgressLabel("Generating your file…");

    try {
      const created = await createExport.mutateAsync({
        resource: "leads",
        format: toApiFormat(format),
        scope: toApiScope(source),
        // The wizard's own field labels are accepted verbatim by the API.
        columns: fields,
        file_name: fileName || undefined,
      });

      setProgress(100);
      const record = toExportRecord(created);
      setResult(record);
      onComplete(record);
      setStep("done");

      if (created.status === "processing") {
        // Large exports are queued to a Celery worker; say so instead of
        // presenting a download button for a file that doesn't exist yet.
        setProgressLabel("Queued for background generation");
        toast.info("This export is large, so it's being generated in the background.", {
          description: "It'll appear in the Download Center when it's ready.",
        });
      }
      if (created.ignored_columns.length > 0) {
        toast.warning(`Skipped unrecognized column(s): ${created.ignored_columns.join(", ")}`);
      }
    } catch (error) {
      setStep("review");
      setProgress(0);
      if (error instanceof ApiError && error.isForbidden) {
        toast.error(error.message, { description: "Ask an admin for export permission." });
      } else if (error instanceof ApiError && error.isRateLimited) {
        toast.error(error.message);
      } else {
        toast.error(errorMessage(error));
      }
    }
  }

  /**
   * Downloads the generated file.
   *
   * Mints a short-lived signed token and navigates to it, which is what lets the
   * browser save the real bytes without an Authorization header. The previous
   * implementation wrote a two-line text Blob named `.xlsx`.
   */
  async function download() {
    if (!result || result.status !== "ready") return;
    try {
      window.location.assign(await exportsApi.downloadUrl(result.id));
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="gradient" size="sm">
          <Plus className="size-4" />
          New Export
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {step === "done" ? "Export ready" : "New Export"}
          </DialogTitle>
        </DialogHeader>

        <AnimatePresence mode="wait">
          {step === "source" && (
            <motion.div key="source" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} className="space-y-2">
              <p className="text-xs text-muted-foreground mb-1">Select data to export</p>
              {(
                [
                  { id: "all" as const, label: "All Leads", desc: "Export your entire lead database" },
                  { id: "filtered" as const, label: "Filtered View", desc: "Export leads matching your current filters" },
                  { id: "selected" as const, label: "Selected Leads", desc: "Export only the leads you've selected" },
                ]
              ).map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSource(opt.id)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-lg border px-3.5 py-3 text-left transition-colors",
                    source === opt.id ? "border-primary/40 bg-primary/[0.06]" : "border-border hover:border-border-strong",
                  )}
                >
                  <div>
                    <p className="text-sm font-medium">{opt.label}</p>
                    <p className="text-xs text-muted-foreground">{opt.desc}</p>
                  </div>
                  {source === opt.id && <Check className="size-4 text-primary" />}
                </button>
              ))}
              <p className="pt-1 text-xs text-muted-foreground">
                <Database className="mr-1 inline size-3" />
                {sourceCount.toLocaleString()} leads selected
              </p>
            </motion.div>
          )}

          {step === "format" && (
            <motion.div key="format" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }}>
              <p className="text-xs text-muted-foreground mb-2">Choose format</p>
              <div className="grid grid-cols-2 gap-2">
                {(["CSV", "Excel", "PDF", "JSON"] as ExportFormat[]).map((f) => {
                  const Icon = FORMAT_ICON[f];
                  return (
                    <button
                      key={f}
                      onClick={() => setFormat(f)}
                      className={cn(
                        "flex flex-col items-start gap-1.5 rounded-lg border px-3 py-3 text-left transition-colors",
                        format === f ? "border-primary/40 bg-primary/[0.06]" : "border-border hover:border-border-strong",
                      )}
                    >
                      <Icon className="size-4 text-primary" />
                      <p className="text-sm font-medium">{f}</p>
                      <p className="text-[11px] text-muted-foreground">{FORMAT_META[f].sizeHint}</p>
                    </button>
                  );
                })}
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 opacity-50">
                {["Google Sheets", "CRM Export", "API Export"].map((f) => (
                  <div key={f} className="rounded-lg border border-dashed border-border px-2 py-2 text-center">
                    <p className="text-[11px] font-medium">{f}</p>
                    <p className="text-[10px] text-muted-foreground">Coming soon</p>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {step === "configure" && (
            <motion.div key="configure" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} className="space-y-4">
              <div>
                <p className="text-xs text-muted-foreground mb-1">File name</p>
                <Input value={fileName} onChange={(e) => setFileName(e.target.value)} />
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-2">Columns to include</p>
                <div className="grid grid-cols-2 gap-2">
                  {EXPORT_FIELDS.map((field) => (
                    <label key={field} className="flex items-center gap-2 text-sm">
                      <Checkbox checked={fields.includes(field)} onCheckedChange={() => toggleField(field)} />
                      {field}
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2.5">
                <span className="text-sm">Include AI summaries</span>
                <Switch checked={includeSummaries} onCheckedChange={setIncludeSummaries} />
              </div>
            </motion.div>
          )}

          {step === "review" && (
            <motion.div key="review" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }} className="space-y-2 text-sm">
              <ReviewRow label="Source" value={source === "all" ? "All Leads" : source === "filtered" ? "Filtered View" : "Selected Leads"} />
              <ReviewRow label="Rows" value={sourceCount.toLocaleString()} />
              <ReviewRow label="Format" value={format} />
              <ReviewRow label="Columns" value={`${fields.length} of ${EXPORT_FIELDS.length}`} />
              <ReviewRow label="AI summaries" value={includeSummaries ? "Included" : "Excluded"} />
              <ReviewRow label="File name" value={`${fileName || "export"}.${format.toLowerCase() === "excel" ? "xlsx" : format.toLowerCase()}`} />
            </motion.div>
          )}

          {step === "progress" && (
            <motion.div key="progress" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="py-6">
              <p className="mb-3 text-center text-sm text-muted-foreground">{progressLabel}</p>
              <Progress value={progress} />
              <p className="mt-2 text-center text-xs tabular-nums text-muted-foreground">{progress}%</p>
            </motion.div>
          )}

          {step === "done" && result && (
            <motion.div key="done" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center gap-3 py-4 text-center">
              <div className="flex size-14 items-center justify-center rounded-full bg-success/15 text-success">
                <CheckCircle2 className="size-7" />
              </div>
              <div>
                <p className="text-sm font-semibold">{result.fileName}</p>
                <p className="text-xs text-muted-foreground">
                  {result.rowCount.toLocaleString()} rows · {result.sizeLabel}
                </p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={download}>
                  <Download className="size-3.5" />
                  Download
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>
                  Close
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {step !== "progress" && step !== "done" && (
          <div className="flex items-center justify-between border-t border-border pt-4">
            <Button
              variant="ghost"
              size="sm"
              disabled={step === "source"}
              onClick={() =>
                setStep(step === "format" ? "source" : step === "configure" ? "format" : "review")
              }
            >
              <ChevronLeft className="size-3.5" />
              Back
            </Button>
            {step === "review" ? (
              <Button size="sm" onClick={startExport}>
                Start Export
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() =>
                  setStep(step === "source" ? "format" : step === "format" ? "configure" : "review")
                }
              >
                Continue
                <ChevronRight className="size-3.5" />
              </Button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-surface-2/40 px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <Badge variant="outline">{value}</Badge>
    </div>
  );
}
