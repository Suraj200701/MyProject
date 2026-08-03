"""CSV writer.

Written with `utf-8-sig` (UTF-8 with BOM) because Excel on Windows otherwise
decodes a plain UTF-8 CSV as cp1252 and mangles every non-ASCII company name.
The BOM costs three bytes and is what makes "export then open in Excel" work by
default. Our own CSV importer decodes `utf-8-sig` first, so an export round-trips
back through `POST /leads/import` without edits.

`\\r\\n` line endings, per RFC 4180 — the format Excel expects.

Multi-section reports are flattened: the primary table first, then each section
separated by a blank line and preceded by its title. CSV has no concept of
sheets, so this is a convention rather than a standard; the XLSX and PDF writers
represent those reports better and are the recommended formats for them.
"""

from __future__ import annotations

import csv
import io

from services.exporters.dataset import Column, Dataset, text_cell


def render(dataset: Dataset) -> bytes:
    buffer = io.StringIO(newline="")
    # QUOTE_MINIMAL matches what spreadsheet tools emit and expect; the csv
    # module handles embedded commas, quotes and newlines correctly.
    writer = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)

    writer.writerow([dataset.title])
    if dataset.subtitle:
        writer.writerow([dataset.subtitle])
    for key, value in dataset.metadata.items():
        writer.writerow([key, text_cell(value)])
    writer.writerow([])

    if dataset.columns:
        _write_table(writer, dataset.columns, dataset.rows)

    for index, section in enumerate(dataset.sections):
        if index or dataset.columns:
            writer.writerow([])
        writer.writerow([section.title])
        if section.note:
            writer.writerow([section.note])
        _write_table(writer, section.columns, section.rows)

    return buffer.getvalue().encode("utf-8-sig")


def _write_table(writer, columns: list[Column], rows: list[dict]) -> None:
    writer.writerow([c.label for c in columns])
    for row in rows:
        writer.writerow([text_cell(row.get(c.key)) for c in columns])
