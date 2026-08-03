"""PDF writer, via ReportLab's platypus document model.

Landscape A4: lead exports are wide (company, industry, city, contact, email,
phone, score, status) and portrait forces column widths that truncate email
addresses, which is the whole point of the row.

Design decisions worth stating:

* **Column widths are proportional to the `Column.width` hints**, then scaled to
  the available frame. A fixed width per column either overflows the page or
  wastes half of it depending on the resource.
* **Cell text is wrapped in `Paragraph`**, not written as a bare string. A bare
  string in a ReportLab table does not wrap — it overflows into the next column
  and the table silently renders unreadable. Wrapping costs some build time and
  is the difference between a usable report and a broken one.
* **Rows are emitted in chunks** (`_ROWS_PER_CHUNK`) as separate tables that each
  repeat the header. `LongTable` can split across pages on its own, but building
  one table of tens of thousands of `Paragraph` flowables is where a big PDF
  export goes quadratic on memory.
* **A hard page budget** (`_MAX_TABLE_ROWS`) caps how much of a large dataset is
  laid out. PDF is a presentation format; a 50,000-row PDF is not something
  anyone reads, and rendering one can take minutes. Past the cap the document
  says so explicitly and points at CSV/XLSX rather than silently truncating.
"""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from services.exporters.dataset import Column, Dataset, ReportSection, format_cell

_PAGE_SIZE = landscape(A4)
_MARGIN = 12 * mm
_ROWS_PER_CHUNK = 250
# ~40 pages at 250 rows/page. Beyond this the reader is better served by a
# spreadsheet, and the note in the document says exactly that.
_MAX_TABLE_ROWS = 10_000

_HEADER_BG = colors.HexColor("#1F2937")
_ROW_ALT_BG = colors.HexColor("#F3F4F6")
_GRID = colors.HexColor("#D1D5DB")
_MUTED = colors.HexColor("#6B7280")

_styles = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("ExportTitle", parent=_styles["Title"], fontSize=16, alignment=TA_LEFT, spaceAfter=2)
_SUBTITLE_STYLE = ParagraphStyle("ExportSubtitle", parent=_styles["Normal"], fontSize=9, textColor=_MUTED, spaceAfter=6)
_META_STYLE = ParagraphStyle("ExportMeta", parent=_styles["Normal"], fontSize=8, textColor=_MUTED, leading=11)
_SECTION_STYLE = ParagraphStyle("ExportSection", parent=_styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
_CELL_STYLE = ParagraphStyle("ExportCell", parent=_styles["Normal"], fontSize=7.5, leading=9.5)
_HEAD_STYLE = ParagraphStyle(
    "ExportHead", parent=_styles["Normal"], fontSize=7.5, leading=9.5, textColor=colors.white, fontName="Helvetica-Bold"
)
_NOTE_STYLE = ParagraphStyle("ExportNote", parent=_styles["Normal"], fontSize=8, textColor=colors.HexColor("#B45309"))


def render(dataset: Dataset) -> bytes:
    stream = io.BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=_PAGE_SIZE,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
        title=dataset.title,
        author="LeadMaster AI",
        subject=dataset.subtitle or dataset.title,
    )

    story: list = [Paragraph(_escape(dataset.title), _TITLE_STYLE)]
    if dataset.subtitle:
        story.append(Paragraph(_escape(dataset.subtitle), _SUBTITLE_STYLE))
    if dataset.metadata:
        meta_line = "  ·  ".join(
            f"<b>{_escape(key)}:</b> {_escape(format_cell(value))}" for key, value in dataset.metadata.items()
        )
        story.append(Paragraph(meta_line, _META_STYLE))
    story.append(Spacer(1, 8))

    frame_width = _PAGE_SIZE[0] - 2 * _MARGIN

    if dataset.columns:
        story.extend(_table_story(dataset.columns, dataset.rows, frame_width))

    for index, section in enumerate(dataset.sections):
        if index or dataset.columns:
            # Each analytics/dashboard section starts on its own page so a
            # report reads as distinct chapters instead of one run-on table.
            story.append(PageBreak())
        story.extend(_section_story(section, frame_width))

    if not dataset.columns and not dataset.sections:
        story.append(Paragraph("This export contained no data.", _CELL_STYLE))

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return stream.getvalue()


def _section_story(section: ReportSection, frame_width: float) -> list:
    story: list = [Paragraph(_escape(section.title), _SECTION_STYLE)]
    if section.note:
        story.append(Paragraph(_escape(section.note), _SUBTITLE_STYLE))
    story.extend(_table_story(section.columns, section.rows, frame_width))
    return story


def _table_story(columns: list[Column], rows: list[dict], frame_width: float) -> list:
    if not columns:
        return []

    col_widths = _column_widths(columns, frame_width)
    header = [Paragraph(_escape(c.label), _HEAD_STYLE) for c in columns]

    if not rows:
        table = Table([header], colWidths=col_widths, repeatRows=1)
        table.setStyle(_table_style(0))
        return [table, Spacer(1, 6), Paragraph("No rows matched this selection.", _META_STYLE)]

    visible = rows[:_MAX_TABLE_ROWS]
    story: list = []

    for start in range(0, len(visible), _ROWS_PER_CHUNK):
        chunk = visible[start : start + _ROWS_PER_CHUNK]
        data = [header]
        for row in chunk:
            data.append([Paragraph(_escape(format_cell(row.get(c.key))), _CELL_STYLE) for c in columns])

        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(_table_style(len(chunk)))
        story.append(table)

    if len(rows) > _MAX_TABLE_ROWS:
        omitted = len(rows) - _MAX_TABLE_ROWS
        story.append(Spacer(1, 8))
        story.append(
            KeepTogether(
                Paragraph(
                    f"Showing the first {_MAX_TABLE_ROWS:,} of {len(rows):,} rows. "
                    f"{omitted:,} further rows were omitted because PDF is a presentation "
                    f"format — re-run this export as CSV or Excel for the complete data set.",
                    _NOTE_STYLE,
                )
            )
        )

    return story


def _table_style(row_count: int) -> TableStyle:
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, _GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    # Zebra striping, applied per row: ROWBACKGROUNDS would also stripe the
    # header row, overwriting its fill.
    for index in range(1, row_count + 1):
        if index % 2 == 0:
            commands.append(("BACKGROUND", (0, index), (-1, index), _ROW_ALT_BG))
    return TableStyle(commands)


def _column_widths(columns: list[Column], frame_width: float) -> list[float]:
    """Distributes the frame width in proportion to each column's width hint."""
    total_hint = sum(max(1, c.width) for c in columns)
    return [frame_width * (max(1, c.width) / total_hint) for c in columns]


def _draw_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(_MUTED)
    canvas.drawString(_MARGIN, _MARGIN * 0.55, "Generated by LeadMaster AI")
    canvas.drawRightString(_PAGE_SIZE[0] - _MARGIN, _MARGIN * 0.55, f"Page {doc.page}")
    canvas.restoreState()


def _escape(text: str) -> str:
    """Escapes ReportLab's inline markup.

    Paragraph parses a mini-HTML dialect, so an unescaped `<` or `&` in real lead
    data (e.g. "Smith & Sons", "<Unnamed>") raises a parse error mid-build and
    fails the whole export.
    """
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
