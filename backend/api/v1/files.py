"""File/document management endpoints: upload, list, metadata, download,
and delete. All routes are org-scoped — documents belonging to another
organization are never visible, downloadable, or deletable."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_organization, get_current_user
from database.session import get_db
from models.document import Document
from models.organization import Organization
from models.user import User
from schemas.common import MessageResponse
from schemas.document import DocumentOut, DocumentUploadResponse
from services import document_service
from utils.exceptions import NotFoundError
from utils.pagination import Page, PaginationParams, pagination_params, paginate

router = APIRouter(prefix="/files", tags=["Files"])


def _to_document_out(document: Document) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        file_name=document.file_name,
        original_name=document.original_name,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
        entity_type=document.entity_type,
        entity_id=document.entity_id,
        created_at=document.created_at,
        download_url=f"/api/v1/files/{document.id}/download",
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    kind: Literal["image", "document"] = Form("document"),
    entity_type: str | None = Form(None),
    entity_id: uuid.UUID | None = Form(None),
    user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    document = await document_service.upload_file(
        db,
        organization_id=organization.id,
        user_id=user.id,
        upload_file=file,
        entity_type=entity_type,
        entity_id=entity_id,
        kind=kind,
    )
    return DocumentUploadResponse(document=_to_document_out(document))


@router.get("", response_model=Page[DocumentOut])
async def list_files(
    entity_type: str | None = None,
    params: PaginationParams = Depends(pagination_params),
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).where(Document.organization_id == organization.id).order_by(Document.created_at.desc())
    if entity_type:
        stmt = stmt.where(Document.entity_type == entity_type)

    rows, meta = await paginate(db, stmt, params)
    return Page(items=[_to_document_out(d) for d in rows], meta=meta)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_file_metadata(
    document_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await document_service.get_document(db, document_id, organization.id)
    return _to_document_out(document)


@router.get("/{document_id}/download")
async def download_file(
    document_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document, path = await document_service.get_download_path(db, document_id, organization.id)
    if not path.exists():
        raise NotFoundError("File content not found in storage")

    return FileResponse(
        path=path,
        media_type=document.mime_type,
        filename=document.original_name,
        headers={"Content-Disposition": f'attachment; filename="{document.original_name}"'},
    )


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_file(
    document_id: uuid.UUID,
    organization: Organization = Depends(get_current_organization),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await document_service.delete_file(db, document_id, organization.id)
    return MessageResponse(message="File deleted successfully")
