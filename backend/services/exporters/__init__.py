"""Format writers for the Export Center.

Each writer takes a `Dataset` and returns `bytes`. They know nothing about leads,
searches or reports, and the dataset builders know nothing about file formats —
so adding a format and adding an exportable resource stay independent.

    from services import exporters
    blob = exporters.render(dataset, ExportFormat.EXCEL)
    name = exporters.build_file_name("my_export", ExportFormat.EXCEL)
"""

from __future__ import annotations

from models.enums import ExportFormat
from services.exporters import csv_exporter, json_exporter, pdf_exporter, xlsx_exporter
from services.exporters.dataset import Column, Dataset, ReportSection

__all__ = [
    "Column",
    "Dataset",
    "ReportSection",
    "render",
    "media_type_for",
    "extension_for",
    "build_file_name",
]

_RENDERERS = {
    ExportFormat.CSV: csv_exporter.render,
    ExportFormat.EXCEL: xlsx_exporter.render,
    ExportFormat.PDF: pdf_exporter.render,
    ExportFormat.JSON: json_exporter.render,
}

# `.xlsx` rather than `.excel` — the enum member is EXCEL but the file extension
# users and Excel itself expect is xlsx. The frontend derives the same mapping.
_EXTENSIONS = {
    ExportFormat.CSV: "csv",
    ExportFormat.EXCEL: "xlsx",
    ExportFormat.PDF: "pdf",
    ExportFormat.JSON: "json",
}

_MEDIA_TYPES = {
    ExportFormat.CSV: "text/csv; charset=utf-8",
    ExportFormat.EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ExportFormat.PDF: "application/pdf",
    ExportFormat.JSON: "application/json",
}


def render(dataset: Dataset, export_format: ExportFormat) -> bytes:
    """Renders `dataset` in `export_format`."""
    try:
        renderer = _RENDERERS[export_format]
    except KeyError:  # pragma: no cover - unreachable while the enum is closed
        raise ValueError(f"No writer registered for format {export_format!r}") from None
    return renderer(dataset)


def media_type_for(export_format: ExportFormat) -> str:
    return _MEDIA_TYPES.get(export_format, "application/octet-stream")


def extension_for(export_format: ExportFormat) -> str:
    return _EXTENSIONS.get(export_format, "bin")



# Extensions that may be *replaced* when the caller's guess disagrees with the
# format actually being written. Deliberately a closed list rather than a
# "looks like an extension" heuristic: a length-based rule silently turns
# "my.company.leads" into "my.company", destroying part of a name the user chose.
# An ugly "report.xls.csv" would be better than that, so only a name ending in a
# recognized export extension is ever rewritten.
_REPLACEABLE_EXTENSIONS = frozenset({"csv", "xlsx", "xls", "xlsm", "pdf", "json", "txt", "tsv"})


def build_file_name(stem: str, export_format: ExportFormat) -> str:
    """Combines a caller-supplied stem with the format's real extension.

    The stem is sanitized by `services.storage.sanitize_filename` before it
    reaches storage; this only ensures the extension matches the bytes, so a
    file named `.csv` is never actually a workbook.
    """
    extension = extension_for(export_format)
    clean = (stem or "export").strip() or "export"
    if clean.lower().endswith(f".{extension}"):
        return clean

    head, _, tail = clean.rpartition(".")
    if head and tail.lower() in _REPLACEABLE_EXTENSIONS:
        clean = head

    return f"{clean}.{extension}"
