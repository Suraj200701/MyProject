"use client";

import * as React from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ExternalLink,
  Info,
  Loader2,
  Monitor,
  Search,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Progress } from "@/components/ui/progress";
import { CsvDropZone } from "@/components/google-maps/csv-drop-zone";
import { ImportHistory } from "@/components/google-maps/import-history";
import { useImportGoogleMapsCsv } from "@/lib/api/queries";
import { buildMapsSearchUrl } from "@/lib/maps-search-url";
import { isDesktop, openExternal } from "@/lib/desktop-bridge";
import type { LeadImportOut } from "@/lib/api/types";

type Step = "search" | "extract" | "import" | "done";

const STEPS: { id: Step; label: string }[] = [
  { id: "search", label: "Search" },
  { id: "extract", label: "Extract" },
  { id: "import", label: "Import" },
  { id: "done", label: "Done" },
];

/**
 * Google Maps Search — open a Maps query, then import what your extractor exported.
 *
 * What this module does **not** do: scrape, fetch or parse Google Maps. It builds
 * a normal `google.com/maps/search/...` link, opens it (embedded window on
 * desktop, new tab on the web), and later accepts the CSV that the user's own
 * browser extension produced. The extraction happens entirely in the user's
 * browser, under their control — LeadMaster never sees Google Maps.
 *
 * Which is why "Start Extraction" does not, and cannot, drive the extension: no
 * web page can invoke another extension's UI. It advances this workflow to the
 * import step and tells the user what to click, rather than pretending to
 * automate something it has no access to.
 */
export function GoogleMapsSearch() {
  const [keyword, setKeyword] = React.useState("");
  const [location, setLocation] = React.useState("");
  const [step, setStep] = React.useState<Step>("search");
  const [file, setFile] = React.useState<File | null>(null);
  const [enrich, setEnrich] = React.useState(false);
  const [result, setResult] = React.useState<LeadImportOut | null>(null);
  const [openFailed, setOpenFailed] = React.useState(false);

  const importCsv = useImportGoogleMapsCsv();
  const mapsUrl = buildMapsSearchUrl(keyword, location);
  const desktop = isDesktop();
  const stepIndex = STEPS.findIndex((s) => s.id === step);

  async function openMaps() {
    if (!mapsUrl) return;
    setOpenFailed(false);
    const opened = await openExternal(mapsUrl);
    if (!opened) {
      // Almost always a popup blocker. The link stays visible so the user has a
      // way through rather than a dead button.
      setOpenFailed(true);
      return;
    }
    setStep("extract");
  }

  function submitImport() {
    if (!file) return;
    importCsv.mutate(
      { file, keyword: keyword.trim() || undefined, location: location.trim() || undefined, enrich },
      {
        onSuccess: (data) => {
          setResult(data);
          setStep("done");
          if (data.imported > 0) {
            toast.success(`Imported ${data.imported} lead${data.imported === 1 ? "" : "s"}`, {
              description: `${data.duplicates_skipped} duplicate(s) skipped.`,
            });
          } else {
            toast.warning("Nothing new was imported", {
              description: `${data.duplicates_skipped} duplicate(s), ${data.invalid_rows} invalid row(s).`,
            });
          }
        },
        onError: (error) => toast.error(error.message),
      },
    );
  }

  function startOver() {
    setFile(null);
    setResult(null);
    setStep("search");
  }

  return (
    <div className="space-y-5">
      {/* Progress across the four steps. */}
      <div className="flex items-center gap-2">
        {STEPS.map((s, index) => (
          <React.Fragment key={s.id}>
            <span
              className={`text-xs font-medium ${
                index <= stepIndex ? "text-foreground" : "text-muted-foreground"
              }`}
            >
              {s.label}
            </span>
            {index < STEPS.length - 1 ? (
              <span className="h-px w-6 bg-border" aria-hidden />
            ) : null}
          </React.Fragment>
        ))}
        <Progress
          value={((stepIndex + 1) / STEPS.length) * 100}
          className="ml-2 h-1 max-w-[160px]"
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* --- Step 1: the search ------------------------------------------ */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Search className="size-4" />
              1. Search Google Maps
            </CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              Opens Google Maps with your query{" "}
              {desktop ? "in an embedded window" : "in a new browser tab"}.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="gm-keyword" className="text-xs">
                  Keyword
                </Label>
                <Input
                  id="gm-keyword"
                  placeholder="dentists"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && mapsUrl) void openMaps();
                  }}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="gm-location" className="text-xs">
                  Location
                </Label>
                <Input
                  id="gm-location"
                  placeholder="Ahmedabad"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && mapsUrl) void openMaps();
                  }}
                />
              </div>
            </div>

            {mapsUrl ? (
              <p className="break-all rounded-lg bg-surface-2/60 px-2.5 py-2 font-mono text-[11px] text-muted-foreground">
                {mapsUrl}
              </p>
            ) : null}

            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" disabled={!mapsUrl} onClick={() => void openMaps()}>
                {desktop ? <Monitor className="size-3.5" /> : <ExternalLink className="size-3.5" />}
                Open Google Maps
              </Button>
              {step !== "search" ? (
                <Badge variant="outline" className="gap-1">
                  <CheckCircle2 className="size-3 text-success" />
                  Opened
                </Badge>
              ) : null}
            </div>

            {openFailed && mapsUrl ? (
              <p className="flex items-start gap-1.5 rounded-lg border border-warning/30 bg-warning/5 p-2.5 text-xs text-warning">
                <AlertTriangle className="mt-0.5 size-3 shrink-0" />
                <span>
                  Your browser blocked the new tab.{" "}
                  <a
                    href={mapsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline"
                    onClick={() => setStep("extract")}
                  >
                    Open Google Maps manually
                  </a>
                  , then continue below.
                </span>
              </p>
            ) : null}
          </CardContent>
        </Card>

        {/* --- Step 2: the user's own extension ---------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="size-4" />
              2. Extract with your extension
            </CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              Extraction runs in your browser, in your own Google Maps Extractor
              extension. LeadMaster never reads Google Maps itself.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <ol className="space-y-1.5 text-xs text-muted-foreground">
              <li>1. In the Google Maps tab, open your extractor extension.</li>
              <li>2. Let it collect the results you want.</li>
              <li>3. Export to CSV — it saves to your Downloads folder.</li>
            </ol>
            <Button
              size="sm"
              variant={step === "extract" ? "default" : "outline"}
              disabled={step === "search"}
              onClick={() => setStep("import")}
            >
              Start Extraction
              <ArrowRight className="size-3.5" />
            </Button>
            <p className="flex items-start gap-1.5 text-[11px] text-muted-foreground">
              <Info className="mt-0.5 size-3 shrink-0" />
              This button can&apos;t drive your extension — no web page is allowed to.
              It moves you to the import step once you&apos;ve exported.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* --- Step 3: import --------------------------------------------- */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">3. Import the CSV</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Leads are deduplicated against your existing database, AI-scored, and saved.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <CsvDropZone
            file={file}
            onFile={setFile}
            onClear={() => setFile(null)}
            disabled={importCsv.isPending}
          />

          <div className="flex items-start justify-between gap-4 rounded-lg border border-border p-3">
            <div className="space-y-0.5">
              <Label htmlFor="gm-enrich" className="text-xs font-medium">
                Enrich from company websites
              </Label>
              <p className="text-[11px] text-muted-foreground">
                Visits each lead&apos;s own site to fill in missing emails, phones and GSTINs.
                Slower — one request per lead.
              </p>
            </div>
            <Switch
              id="gm-enrich"
              checked={enrich}
              onCheckedChange={setEnrich}
              disabled={importCsv.isPending}
            />
          </div>

          <div className="flex items-center gap-2">
            <Button size="sm" disabled={!file || importCsv.isPending} onClick={submitImport}>
              {importCsv.isPending ? <Loader2 className="size-3.5 animate-spin" /> : null}
              {importCsv.isPending ? "Importing…" : "Import leads"}
            </Button>
            {result ? (
              <Button size="sm" variant="ghost" onClick={startOver}>
                New search
              </Button>
            ) : null}
          </div>

          {importCsv.isPending ? (
            <p className="text-xs text-muted-foreground">
              Parsing, deduplicating and scoring
              {enrich ? ", then visiting each website" : ""}. Large files take a moment.
            </p>
          ) : null}

          {result ? <ImportSummary result={result} /> : null}
        </CardContent>
      </Card>

      <ImportHistory />
    </div>
  );
}

function ImportSummary({ result }: { result: LeadImportOut }) {
  const nothingLanded = result.imported === 0;

  return (
    <div
      className={`rounded-lg border p-3 ${
        nothingLanded ? "border-warning/30 bg-warning/5" : "border-success/30 bg-success/5"
      }`}
    >
      <p className="flex items-center gap-1.5 text-sm font-medium">
        {nothingLanded ? (
          <AlertTriangle className="size-4 text-warning" />
        ) : (
          <CheckCircle2 className="size-4 text-success" />
        )}
        {nothingLanded
          ? "Nothing new was imported"
          : `Imported ${result.imported} lead${result.imported === 1 ? "" : "s"}`}
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <Stat label="Rows in file" value={result.total_rows} />
        <Stat label="Imported" value={result.imported} />
        <Stat label="Duplicates" value={result.duplicates_skipped} />
        <Stat label="Invalid rows" value={result.invalid_rows} />
        {result.enriched > 0 ? <Stat label="Enriched" value={result.enriched} /> : null}
      </dl>

      {result.row_errors && result.row_errors.length > 0 ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-muted-foreground">
            {result.row_errors.length} row issue(s)
          </summary>
          <ul className="mt-1.5 space-y-1">
            {result.row_errors.map((error) => (
              <li key={`${error.line}-${error.message}`} className="text-[11px] text-muted-foreground">
                <span className="font-mono">line {error.line}</span>
                {error.company ? ` · ${error.company}` : ""} — {error.message}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-semibold tabular-nums text-foreground">{value.toLocaleString()}</dd>
    </div>
  );
}
