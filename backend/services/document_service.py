"""Business logic for uploading, listing, downloading, and deleting files.

Physical bytes are delegated to the pluggable `StorageBackend`
(services/storage.py); this module owns validation and the `Document`
metadata row.
"""

import io
import uuid
from pathlib import Path
from typing import Literal

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.document import Document
from services.storage import generate_storage_key, get_storage_backend, sanitize_filename
from utils.exceptions import BadRequestError, NotFoundError

FileKind = Literal["image", "document"]


async def upload_file(
    db: AsyncSession,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    upload_file: UploadFile,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    kind: FileKind = "document",
) -> Document:
    content = await upload_file.read()

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise BadRequestError(f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}mb limit")

    # Never trust the client-supplied content-type alone for anything
    # security-sensitive; it's only used here as a first-pass filter, and
    # for images it's re-verified below by actually decoding the bytes.
    content_type = upload_file.content_type or ""
    allowed_types = settings.allowed_image_types_list if kind == "image" else settings.allowed_document_types_list
    if content_type not in allowed_types:
        raise BadRequestError("Unsupported file type")

    if kind == "image":
        try:
            with Image.open(io.BytesIO(content)) as img:
                img.verify()
        except UnidentifiedImageError as exc:
            raise BadRequestError("Unsupported file type") from exc
        except Exception as exc:  # noqa: BLE001 - any decode failure means an invalid image
            raise BadRequestError("Unsupported file type") from exc

    original_name = sanitize_filename(upload_file.filename or "file")
    storage_key = generate_storage_key(organization_id, original_name, entity_type)

    backend = get_storage_backend()
    storage_path = await backend.save(content, storage_key)

    document = Document(
        organization_id=organization_id,
        user_id=user_id,
        file_name=storage_key.rsplit("/", 1)[-1],
        original_name=original_name,
        mime_type=content_type,
        size_bytes=len(content),
        storage_backend="local",
        storage_path=storage_path,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def _get_org_document(db: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID) -> Document:
    stmt = select(Document).where(Document.id == document_id, Document.organization_id == organization_id)
    document = (await db.execute(stmt)).scalar_one_or_none()
    if document is None:
        raise NotFoundError("Document not found")
    return document


async def get_document(db: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID) -> Document:
    return await _get_org_document(db, document_id, organization_id)


async def delete_file(db: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    document = await _get_org_document(db, document_id, organization_id)

    backend = get_storage_backend()
    key = _storage_key_from_path(document)
    await backend.delete(key)

    await db.delete(document)
    await db.commit()


async def get_download_path(db: AsyncSession, document_id: uuid.UUID, organization_id: uuid.UUID) -> tuple[Document, Path]:
    document = await _get_org_document(db, document_id, organization_id)
    backend = get_storage_backend()
    key = _storage_key_from_path(document)
    return document, backend.get_path(key)


def _storage_key_from_path(document: Document) -> str:
    """Recovers the storage key from the persisted `storage_path`.

    `LocalStorageBackend.save()` records the on-disk path (base_dir/key)
    as `storage_path`, so the key is that path relative to `UPLOAD_DIR`.
    Kept in one place so a future backend swap only needs to update this
    helper (or store the key directly on the row) rather than every call
    site.
    """
    path = Path(document.storage_path)
    try:
        return path.relative_to(Path(settings.UPLOAD_DIR)).as_posix()
    except ValueError:
        # Already a bare key (e.g. a future backend storing keys, not paths).
        return path.as_posix()
