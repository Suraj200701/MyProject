"""Schemas for import runs and the Google Maps search helper."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from models.enums import ImportSource, ImportStatus


class MapsSearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)


class MapsSearchUrlOut(BaseModel):
    """The Google Maps URL to open, plus the query it encodes.

    LeadMaster only builds this link — it never fetches or parses Google Maps.
    """

    url: str
    keyword: str
    location: str | None = None


class ImportRowErrorOut(BaseModel):
    line: int
    message: str
    company: str | None = None


class LeadImportOut(BaseModel):
    id: uuid.UUID
    source: ImportSource
    status: ImportStatus
    file_name: str | None = None
    file_size_bytes: int | None = None
    keyword: str | None = None
    location: str | None = None
    total_rows: int
    imported: int
    duplicates_skipped: int
    invalid_rows: int
    enriched: int
    row_errors: list[ImportRowErrorOut] | None = None
    dedup_signals: dict[str, int] | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
