"""JSON writer.

The integration-oriented format: values keep their types where JSON has one
(numbers stay numbers, booleans stay booleans) rather than being stringified for
display, so a consumer can process the file without re-parsing text. Only types
JSON cannot express — datetimes, Decimals, sets — are converted, and datetimes
use ISO-8601 so they round-trip.

No formula neutralization here: nothing evaluates a JSON string, so escaping a
leading `=` would corrupt the value for the programmatic consumers this format
exists for.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from services.exporters.dataset import Column, Dataset


def render(dataset: Dataset) -> bytes:
    payload = {
        "title": dataset.title,
        "subtitle": dataset.subtitle,
        "generated_at": dataset.generated_at.isoformat(),
        "metadata": dataset.metadata,
        "row_count": dataset.row_count,
    }

    if dataset.columns:
        payload["columns"] = _columns(dataset.columns)
        payload["rows"] = [_row(row, dataset.columns) for row in dataset.rows]

    if dataset.sections:
        payload["sections"] = [
            {
                "title": section.title,
                "note": section.note,
                "columns": _columns(section.columns),
                "rows": [_row(row, section.columns) for row in section.rows],
            }
            for section in dataset.sections
        ]

    return json.dumps(payload, indent=2, ensure_ascii=False, default=_fallback).encode("utf-8")


def _columns(columns: list[Column]) -> list[dict]:
    return [{"key": c.key, "label": c.label} for c in columns]


def _row(row: dict, columns: list[Column]) -> dict:
    """Projects a row onto the selected columns, keyed by column key.

    Restricting to `columns` matters: it is what makes the "choose which columns
    to export" option actually withhold the unselected fields, rather than
    shipping the full row and only hiding them in the other formats.
    """
    return {c.key: _value(row.get(c.key)) for c in columns}


def _value(value: object):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        as_float = float(value)
        return int(as_float) if as_float.is_integer() else as_float
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (set, frozenset, tuple)):
        return [_value(v) for v in value]
    if isinstance(value, list):
        return [_value(v) for v in value]
    return value


def _fallback(value: object) -> str:
    """Last resort for anything `_value` did not anticipate."""
    return str(value)
