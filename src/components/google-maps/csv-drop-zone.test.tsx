import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CsvDropZone } from "./csv-drop-zone";

function csvFile(name = "export.csv") {
  return new File(["Name,Address\nAcme,MG Road"], name, { type: "text/csv" });
}

afterEach(() => {
  // showOpenFilePicker is assigned per-test; remove it so the "unsupported"
  // branch is reachable again.
  delete (window as unknown as Record<string, unknown>).showOpenFilePicker;
  delete (window as unknown as Record<string, unknown>).leadmaster;
});

describe("CsvDropZone", () => {
  it("shows the prompt when no file is selected", () => {
    render(<CsvDropZone file={null} onFile={vi.fn()} onClear={vi.fn()} />);
    expect(screen.getByText(/drop your exported csv here/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /choose file/i })).toBeInTheDocument();
  });

  it("accepts a CSV chosen through the file input", async () => {
    const onFile = vi.fn();
    render(<CsvDropZone file={null} onFile={onFile} onClear={vi.fn()} />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, csvFile());

    expect(onFile).toHaveBeenCalledOnce();
    expect(onFile.mock.calls[0][0].name).toBe("export.csv");
  });

  /**
   * Extension exports are CSV but browsers label them inconsistently
   * (`application/vnd.ms-excel` when Excel is installed). Rejecting on MIME type
   * would block legitimate files, so the extension is what's checked.
   */
  it("accepts a .csv file even when the browser reports an Excel MIME type", async () => {
    const onFile = vi.fn();
    render(<CsvDropZone file={null} onFile={onFile} onClear={vi.fn()} />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(
      input,
      new File(["a,b"], "maps.csv", { type: "application/vnd.ms-excel" }),
    );

    expect(onFile).toHaveBeenCalledOnce();
  });

  /**
   * Dropped, not chosen: the file input carries `accept=".csv"`, so the OS dialog
   * (and `userEvent.upload`, which honours the attribute) already filters
   * non-CSVs out. Drag-and-drop bypasses `accept` entirely, which makes it the
   * only route a wrong file can actually arrive by — and therefore the one worth
   * asserting on.
   */
  it("rejects a dropped non-CSV file with an explanation rather than ignoring it", async () => {
    const onFile = vi.fn();
    render(<CsvDropZone file={null} onFile={onFile} onClear={vi.fn()} />);

    const zone = screen.getByText(/drop your exported csv here/i).closest("div")!;
    fireEvent.drop(zone, {
      dataTransfer: { files: [new File(["{}"], "leads.json", { type: "application/json" })] },
    });

    expect(onFile).not.toHaveBeenCalled();
    expect(await screen.findByText(/isn't a CSV/i)).toBeInTheDocument();
  });

  it("accepts a dropped CSV", async () => {
    const onFile = vi.fn();
    render(<CsvDropZone file={null} onFile={onFile} onClear={vi.fn()} />);

    const zone = screen.getByText(/drop your exported csv here/i).closest("div")!;
    fireEvent.drop(zone, { dataTransfer: { files: [csvFile("dropped.csv")] } });

    await waitFor(() => expect(onFile).toHaveBeenCalledOnce());
    expect(onFile.mock.calls[0][0].name).toBe("dropped.csv");
  });

  it("shows the selected file with a way to remove it", async () => {
    const onClear = vi.fn();
    render(<CsvDropZone file={csvFile("maps-export.csv")} onFile={vi.fn()} onClear={onClear} />);

    expect(screen.getByText("maps-export.csv")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /remove file/i }));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it("hides the Downloads shortcut when the browser has no file-picker API", () => {
    render(<CsvDropZone file={null} onFile={vi.fn()} onClear={vi.fn()} />);
    // Firefox/Safari: showOpenFilePicker is absent, so offering the button would
    // be a dead end.
    expect(screen.queryByRole("button", { name: /open downloads/i })).not.toBeInTheDocument();
  });

  it("offers a Downloads shortcut when showOpenFilePicker exists", async () => {
    const onFile = vi.fn();
    const getFile = vi.fn().mockResolvedValue(csvFile("from-downloads.csv"));
    const picker = vi.fn().mockResolvedValue([{ getFile }]);
    (window as unknown as Record<string, unknown>).showOpenFilePicker = picker;

    render(<CsvDropZone file={null} onFile={onFile} onClear={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /open downloads/i }));

    // startIn: "downloads" is the whole point — it opens where the export landed.
    expect(picker).toHaveBeenCalledWith(expect.objectContaining({ startIn: "downloads" }));
    await waitFor(() => expect(onFile).toHaveBeenCalledOnce());
    expect(onFile.mock.calls[0][0].name).toBe("from-downloads.csv");
  });

  it("stays quiet when the user dismisses the picker", async () => {
    const onFile = vi.fn();
    (window as unknown as Record<string, unknown>).showOpenFilePicker = vi
      .fn()
      .mockRejectedValue(new DOMException("The user aborted a request.", "AbortError"));

    render(<CsvDropZone file={null} onFile={onFile} onClear={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /open downloads/i }));

    expect(onFile).not.toHaveBeenCalled();
    expect(screen.queryByText(/isn't a CSV/i)).not.toBeInTheDocument();
  });

  it("accepts a CSV pushed by the desktop download watcher", async () => {
    const onFile = vi.fn();
    let push: ((file: File) => void) | undefined;
    (window as unknown as Record<string, unknown>).leadmaster = {
      openMapsWindow: vi.fn(),
      watchDownloads: (cb: (file: File) => void) => {
        push = cb;
        return () => {};
      },
    };

    render(<CsvDropZone file={null} onFile={onFile} onClear={vi.fn()} />);
    push?.(csvFile("watched.csv"));

    await waitFor(() => expect(onFile).toHaveBeenCalledOnce());
    expect(onFile.mock.calls[0][0].name).toBe("watched.csv");
  });
});
