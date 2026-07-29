"""Pydantic schemas for the file/document management module."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    file_name: str
    original_name: str
    mime_type: str
    size_bytes: int
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    created_at: datetime
    download_url: str

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    success: bool = True
    document: DocumentOut
