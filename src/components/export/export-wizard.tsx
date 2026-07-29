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
import { cn } from "@/lib/utils";
import { mockLeads } from "@/lib/mock-data";
import { EXPORT_FIELDS, type ExportFormat, type ExportRecord, type ExportSource } from "@/components/export/types";
import { FORMAT_META } from "@/components/export/mock-data";

const FORMAT_ICON: Record<ExportFormat, typeof FileText> = {
  CSV: Sheet,
  Excel: FileSpreadsheet,
  PDF: FileText,
  JSON: Braces,
};

const PROGRESS_LABELS = ["Preparing data…", "Formatting rows…", "Generating file…", "Finalizing…"];

type Step = "source" | "format" | "configure" | "review" | "progress" | "done";

function delay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

export function ExportWizard({ onComplete }: { onComplete: (record: ExportRecord) => void }) {
  const [open, setOpen] = React.useState(false);
  const [step, setStep] = React.useState<Step>("source");
  const [source, setSource] = React.useState<ExportSource>("all");
  const [format, setFormat] = React.useState<ExportFormat>("CSV");
  const [fields, setFields] = React.useState<string[]>([...EXPORT_FIELDS]);
  const [fileName, setFileName] = React.useState("leadmaster_export");
  const [includeSummaries, setIncludeSummaries] = React.useState(true);
  const [progress, setProgress] = React.useState(0);
  const [progressLabel, setProgressLabel] = React.useState(PROGRESS_LABELS[0]);
  const [result, setResult] = React.useState<ExportRecord | null>(null);

  const sourceCount = source === "all" ? mockLeads.length : source === "filtered" ? Math.round(mockLeads.length * 0.4) : 12;

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

  async function startExport() {
    setStep("progress");
    for (let i = 0; i < PROGRESS_LABELS.length; i++) {
      setProgressLabel(PROGRESS_LABELS[i]);
      await delay(500);
      setProgress(Math.round(((i + 1) / PROGRESS_LABELS.length) * 100));
    }
    await delay(300);

    const record: ExportRecord = {
      id: `exp-${Date.now()}`,
      fileName: `${fileName || "export"}.${format.toLowerCase() === "excel" ? "xlsx" : format.toLowerCase()}`,
      format,
      rowCount: sourceCount,
      sizeLabel: `${(sourceCount * 4.2).toFixed(0)} KB`,
      createdAt: new Date().toISOString(),
      status: "ready",
    };
    setResult(record);
    onComplete(record);
    setStep("done");
  }

  function download() {
    if (!result) return;
    const blob = new Blob([`LeadMaster AI export — ${result.fileName}\nRows: ${result.rowCount}\n`], {
      type: "text/plain",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = result.fileName;
    link.click();
    URL.revokeObjectURL(link.href);
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
