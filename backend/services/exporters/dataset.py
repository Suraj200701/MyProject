"""The format-independent shape every exporter renders.

One `Dataset` describes a whole document. Writers consume it and know nothing
about leads, searches or reports — which is what keeps "add a format" and "add
an exportable resource" independent of each other.

Two document shapes fit in the same structure:

* **Tabular** (leads, search results) — `columns` + `rows`, no sections.
* **Report** (dashboard, analytics) — a `metadata` summary block plus several
  `sections`, each its own small table. `columns`/`rows` may be empty.

Cell-value contract
-------------------
Row dicts hold real Python values (`int`, `float`, `Decimal`, `datetime`, `str`,
`None`, `list[str]`), *not* pre-formatted strings. Each writer decides how to
present them — XLSX keeps numbers and dates native so Excel can sort and format
them, whereas CSV and PDF need text. Pre-formatting here would throw that away.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class Column:
    """One column: where to read it, what to call it, how wide to draw it."""

    key: str
    label: str
    # Character-width hint for XLSX column sizing and PDF column proportions.
    # Ignored by CSV and JSON.
    width: int = 18


@dataclass
class ReportSection:
    """A named sub-table. Used by multi-part reports."""

    title: str
    columns: list[Column]
    rows: list[dict]
    # Optional prose shown under the section heading in PDF/XLSX.
    note: str | None = None


@dataclass
class Dataset:
    """A complete export document."""

    title: str
    columns: list[Column] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    subtitle: str | None = None
    sections: list[ReportSection] = field(default_factory=list)
    # Ordered key/value summary (organization, generated-at, applied filters).
    # Rendered as a header block in PDF/XLSX and as leading comment-ish rows in
    # CSV, so a file is self-describing once it has left the product.
    metadata: dict[str, str] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def row_count(self) -> int:
        """Total data rows across the primary table and every section.

        This is what gets recorded as `Export.row_count` and what the row cap is
        enforced against, so a 40-section report can't slip past the limit by
        having an empty primary table.
        """
        return len(self.rows) + sum(len(s.rows) for s in self.sections)

    @property
    def is_report(self) -> bool:
        return bool(self.sections) and not self.rows


# --- Cell coercion --------------------------------------------------------

# Leading characters that make a spreadsheet treat a cell as a formula. Lead
# data is attacker-influenced (company names arrive from third-party providers
# and from user-supplied CSV imports), so any of these reaching a raw cell is a
# CSV/XLSX injection vector: the recipient opens the file and Excel executes it.
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def neutralize_formula(text: str) -> str:
    """Defuses spreadsheet formula injection by prefixing a single quote.

    Excel and LibreOffice both treat a leading `'` as "this is text", strip it
    on display, and do not evaluate the rest — so `=cmd|'/c calc'!A1` exports as
    inert text instead of a command the recipient's spreadsheet runs.

    Applied by the CSV and XLSX writers. Not needed for JSON (no evaluator) or
    PDF (not executable).
    """
    if text.startswith(_FORMULA_TRIGGERS):
        return f"'{text}"
    return text


def format_cell(value: object) -> str:
    """Renders a cell value as display text for the text-based formats."""
    if value is None:
        return ""
    if isinstance(value, bool):
        # Checked before int: bool is an int subclass, and "True" reads better
        # than "1" in an exported report.
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        # Trim a trailing ".0" so a rating of 4 doesn't read as "4.0".
        as_float = float(value)
        return str(int(as_float)) if as_float.is_integer() else str(as_float)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(format_cell(v) for v in value if v is not None)
    if isinstance(value, dict):
        return "; ".join(f"{k}={format_cell(v)}" for k, v in value.items())
    return str(value)


def text_cell(value: object) -> str:
    """`format_cell` plus formula neutralization. For CSV and XLSX text."""
    return neutralize_formula(format_cell(value))
