"""Pydantic schemas for the Export Center.

`ExportOut` mirrors the frontend's `ExportRecord` shape
(src/components/export/types.ts) field-for-field, in the same way `LeadOut`
mirrors the frontend `Lead` type — see docs/FRONTEND_BACKEND_MAPPING.md for the
per-field correspondence. Field names stay snake_case, matching every other
schema in this backend.

`size_label` is served pre-formatted alongside the raw `size_bytes`: the download
list renders a human string ("1.2 MB"), and formatting it here means the number
shown always matches the number recorded, with no duplicated rounding rules in
the client.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from models.enums import ExportFormat, ExportResource, ExportStatus

# Mirrors the frontend wizard's `ExportSource` union.
ExportScope = Literal["all", "filtered", "selected"]


class ExportFilters(BaseModel):
    """Lead filters for a `scope="filtered"` export.

    Intentionally the same parameters `GET /leads` accepts, so "export this
    filtered view" produces exactly the rows the table is showing. Send the same
    values the list request used.
    """

    search: str | None = Field(default=None, max_length=255, description="Company-name substring match")
    industry: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)
    min_score: int | None = Field(default=None, ge=0, le=100)
    max_score: int | None = Field(default=None, ge=0, le=100)
    sort_by: Literal["created_at", "lead_score", "company"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"


class ExportCreate(BaseModel):
    """Request body for `POST /exports`."""

    resource: ExportResource = Field(
        default=ExportResource.LEADS,
        description=(
            "What to export. 'leads' honours scope/filters/lead_ids; "
            "'search_results' requires search_id; the two report resources ignore "
            "scope and filters."
        ),
    )
    format: ExportFormat = Field(default=ExportFormat.CSV, description="csv | excel | pdf | json")
    scope: ExportScope = Field(
        default="all",
        description="'all' = every lead in the organization, 'filtered' = apply `filters`, 'selected' = only `lead_ids`",
    )
    lead_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Required when scope='selected'. Ignored otherwise.",
    )
    filters: ExportFilters | None = Field(
        default=None, description="Applied when scope='filtered'. Same parameters as GET /leads."
    )
    search_id: uuid.UUID | None = Field(
        default=None, description="Required when resource='search_results'."
    )
    columns: list[str] = Field(
        default_factory=list,
        description=(
            "Columns to include, in order. Accepts API keys ('lead_score') or the "
            "display labels the export wizard uses ('Lead Score'). Empty = a "
            "sensible default set. Unrecognized names are ignored and reported in "
            "`ignored_columns`."
        ),
    )
    file_name: str | None = Field(
        default=None,
        max_length=120,
        description="File name stem. The correct extension for the format is always appended.",
    )

    @field_validator("lead_ids")
    @classmethod
    def _cap_lead_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        # A selected-lead export is driven by a table selection; an unbounded id
        # list would let one request build an arbitrarily large IN clause.
        if len(value) > 10_000:
            raise ValueError("lead_ids cannot contain more than 10000 ids — use scope='filtered' instead")
        return value

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "resource": "leads",
                    "format": "excel",
                    "scope": "filtered",
                    "filters": {"industry": "Electrical", "min_score": 60, "sort_by": "lead_score", "sort_order": "desc"},
                    "columns": ["Company", "Industry", "City", "Email", "Phone", "Lead Score"],
                    "file_name": "electrical_high_score",
                },
                {
                    "resource": "leads",
                    "format": "csv",
                    "scope": "selected",
                    "lead_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
                },
                {"resource": "search_results", "format": "csv", "search_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"},
                {"resource": "dashboard_report", "format": "pdf"},
                {"resource": "analytics_report", "format": "excel"},
            ]
        }
    }


class ExportOut(BaseModel):
    """One export log row. Mirrors the frontend `ExportRecord`."""

    id: uuid.UUID
    file_name: str
    format: ExportFormat
    resource: ExportResource
    row_count: int
    size_bytes: int
    size_label: str = Field(description='Human-readable size, e.g. "1.2 MB"')
    status: ExportStatus
    download_count: int
    created_at: datetime
    expires_at: datetime | None = None
    error_message: str | None = None
    download_url: str | None = Field(
        default=None,
        description=(
            "Download path, **root-relative** (starts with /api/v1/...). Join it "
            "against the server ORIGIN, not against an API base that already ends "
            "in /api/v1, or the request resolves to /api/v1/api/v1/... and 404s. "
            "Null unless status is 'ready'."
        ),
    )
    ignored_columns: list[str] = Field(
        default_factory=list,
        description="Column names in the request that matched nothing and were skipped.",
    )

    model_config = {"from_attributes": True}


class DownloadTokenOut(BaseModel):
    """A short-lived token for downloading without an Authorization header."""

    token: str
    expires_in: int = Field(description="Seconds until the token stops working")
    download_url: str = Field(
        description=(
            "Ready-to-use root-relative URL with the token attached — assign it "
            "straight to an <a href>. Join against the ORIGIN, not an /api/v1 base."
        )
    )


def format_size(size_bytes: int) -> str:
    """Formats a byte count the way the download list displays it.

    Matches the frontend's convention: no decimal for bytes and KB, one decimal
    from MB up, so "410 KB" and "1.2 MB" both read naturally.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    kilobytes = size_bytes / 1024
    if kilobytes < 1024:
        return f"{kilobytes:.0f} KB"
    megabytes = kilobytes / 1024
    if megabytes < 1024:
        return f"{megabytes:.1f} MB"
    return f"{megabytes / 1024:.1f} GB"
