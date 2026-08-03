"use client";

import * as React from "react";
import { FileSpreadsheet, FolderOpen, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { canWatchDownloads } from "@/lib/desktop-bridge";

/**
 * File System Access API — Chromium only, and only on a secure context.
 *
 * `startIn: "downloads"` opens the picker directly in the Downloads folder,
 * which is the closest a *web* page can get to "detect the downloaded file".
 * Browsers deliberately expose no way to read the download directory, so
 * genuine auto-detection needs the desktop shell (see `desktop-bridge`).
 */
interface FileSystemAccessWindow {
  showOpenFilePicker?: (options?: {
    multiple?: boolean;
    startIn?: string;
    types?: { description: string; accept: Record<string, string[]> }[];
  }) => Promise<{ getFile: () => Promise<File> }[]>;
}

function supportsDownloadsPicker(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof (window as unknown as FileSystemAccessWindow).showOpenFilePicker === "function"
  );
}

function isCsv(file: File): boolean {
  // Content type is unreliable for CSV (Excel installed => vnd.ms-excel), so the
  // extension is the primary signal and the backend parser is the real gate.
  return file.name.toLowerCase().endsWith(".csv") || file.type.includes("csv");
}

export function CsvDropZone({
  file,
  onFile,
  onClear,
  disabled,
}: {
  file: File | null;
  onFile: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
}) {
  const [dragging, setDragging] = React.useState(false);
  const [rejected, setRejected] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const accept = React.useCallback(
    (candidate: File | null | undefined) => {
      if (!candidate) return;
      if (!isCsv(candidate)) {
        setRejected(`"${candidate.name}" isn't a CSV. Export as CSV and try again.`);
        return;
      }
      setRejected(null);
      onFile(candidate);
    },
    [onFile],
  );

  // The desktop shell can tell us when a CSV lands in Downloads. On the web this
  // never fires, and the picker below is the fallback.
  React.useEffect(() => {
    if (!canWatchDownloads()) return;
    return window.leadmaster?.watchDownloads?.((downloaded) => accept(downloaded));
  }, [accept]);

  async function pickFromDownloads() {
    const picker = (window as unknown as FileSystemAccessWindow).showOpenFilePicker;
    if (!picker) {
      inputRef.current?.click();
      return;
    }
    try {
      const [handle] = await picker({
        multiple: false,
        startIn: "downloads",
        types: [{ description: "CSV", accept: { "text/csv": [".csv"] } }],
      });
      accept(await handle.getFile());
    } catch {
      // The user dismissed the picker — not an error worth reporting.
    }
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!disabled) accept(e.dataTransfer.files?.[0]);
        }}
        className={`rounded-xl border border-dashed p-6 text-center transition-colors ${
          dragging ? "border-primary bg-primary/5" : "border-border bg-surface-2/40"
        } ${disabled ? "opacity-60" : ""}`}
      >
        {file ? (
          <div className="flex items-center justify-center gap-2 text-sm">
            <FileSpreadsheet className="size-4 text-success" />
            <span className="font-medium">{file.name}</span>
            <span className="text-muted-foreground">
              ({(file.size / 1024).toFixed(0)} KB)
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="size-6"
              aria-label="Remove file"
              disabled={disabled}
              onClick={onClear}
            >
              <X className="size-3.5" />
            </Button>
          </div>
        ) : (
          <>
            <Upload className="mx-auto size-6 text-muted-foreground" />
            <p className="mt-2 text-sm font-medium">Drop your exported CSV here</p>
            <p className="mt-1 text-xs text-muted-foreground">
              The file your Google Maps extractor extension saved.
            </p>
            <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={disabled}
                onClick={() => inputRef.current?.click()}
              >
                Choose file
              </Button>
              {supportsDownloadsPicker() ? (
                <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={pickFromDownloads}>
                  <FolderOpen className="size-3.5" />
                  Open Downloads
                </Button>
              ) : null}
            </div>
          </>
        )}

        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            accept(e.target.files?.[0]);
            // Reset so re-picking the same filename fires onChange again.
            e.target.value = "";
          }}
        />
      </div>

      {rejected ? <p className="text-xs text-danger">{rejected}</p> : null}
    </div>
  );
}
