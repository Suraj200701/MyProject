"""Pluggable file storage abstraction.

`StorageBackend` defines the contract every backend must satisfy.
`LocalStorageBackend` is the only implementation for now (files live on
local disk under `settings.UPLOAD_DIR`). Swapping in S3 (or any other
object store) later means adding a new class that satisfies the same
`Protocol` and pointing `get_storage_backend()` at it — no changes needed
anywhere that calls the backend (services/document_service.py, etc.).
"""

import re
import uuid
from pathlib import Path
from typing import Protocol, runtime_checkable

import anyio

from config.settings import settings

# Filenames longer than this (excluding extension) get truncated before
# being folded into the storage key, so pathological client-supplied
# names can't blow up the filesystem's max path/filename length.
_MAX_STEM_LENGTH = 100


@runtime_checkable
class StorageBackend(Protocol):
    """Contract every storage backend (local disk, S3, ...) must implement."""

    async def save(self, file_bytes: bytes, key: str) -> str:
        """Persists `file_bytes` under `key` and returns the storage path/URL
        that should be recorded on the `Document` row (`storage_path`)."""
        ...

    async def delete(self, key: str) -> None:
        """Removes the object identified by `key`. Must not raise if the
        object is already missing (delete is idempotent)."""
        ...

    def get_path(self, key: str) -> Path:
        """Returns a local filesystem `Path` for reading/streaming the file
        back. Only meaningful for backends that expose a local path (S3
        would instead expose a presigned URL / stream — see note below)."""
        ...


class LocalStorageBackend:
    """Stores files on local disk under `{settings.UPLOAD_DIR}/{key}`.

    Tradeoff note: writes/deletes use plain synchronous `open()` calls
    wrapped in `anyio.to_thread.run_sync` so they don't block the event
    loop under load. This adds a small amount of overhead (thread hop)
    compared to a bare synchronous write, but for a scope like this
    (local-disk storage, no `aiofiles` dependency available) it's the
    right default: it keeps the backend's public methods genuinely async
    without pulling in a new dependency, and it's a one-line change to
    revert to a plain synchronous write if profiling ever shows the
    thread hop isn't worth it.
    """

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir if base_dir is not None else settings.UPLOAD_DIR)

    def get_path(self, key: str) -> Path:
        return self.base_dir / key

    async def save(self, file_bytes: bytes, key: str) -> str:
        path = self.get_path(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                f.write(file_bytes)

        await anyio.to_thread.run_sync(_write)
        return str(path)

    async def delete(self, key: str) -> None:
        path = self.get_path(key)

        def _delete() -> None:
            path.unlink(missing_ok=True)

        await anyio.to_thread.run_sync(_delete)


def sanitize_filename(original_filename: str) -> str:
    """Strips path separators/traversal segments and limits length so a
    client-supplied filename can never be used to escape the intended
    storage directory or create absurdly long paths.

    Never trust `original_filename` for anything security-sensitive
    beyond display purposes without running it through this first.
    """
    # Keep only the final path component — drops any directory traversal
    # (../, ..\, absolute paths, etc.) regardless of OS path semantics.
    name = original_filename.replace("\\", "/").split("/")[-1].strip()

    if not name or name in (".", ".."):
        name = "file"

    stem = Path(name).stem
    suffix = Path(name).suffix

    # Allow a conservative character set only; everything else becomes "_".
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)[:_MAX_STEM_LENGTH] or "file"
    suffix = re.sub(r"[^A-Za-z0-9.]", "", suffix)[:20]

    return f"{stem}{suffix}"


def generate_storage_key(
    organization_id: uuid.UUID, original_filename: str, entity_type: str | None = None
) -> str:
    """Builds a collision-free, path-traversal-safe storage key:
    `{organization_id}/{entity_type or 'general'}/{uuid4()}_{sanitized_filename}`.
    """
    safe_name = sanitize_filename(original_filename)
    segment = entity_type.strip() if entity_type and entity_type.strip() else "general"
    # Defense in depth: entity_type is client-supplied too, so scrub it
    # the same way we scrub the filename stem before using it as a path
    # segment.
    segment = re.sub(r"[^A-Za-z0-9_-]", "_", segment)[:50] or "general"

    return f"{organization_id}/{segment}/{uuid.uuid4()}_{safe_name}"


def get_storage_backend() -> StorageBackend:
    """Factory for the active storage backend.

    --- S3 seam ---
    To move to S3, implement a class alongside `LocalStorageBackend`:

        class S3StorageBackend:
            def __init__(self, bucket: str, region: str, access_key: str,
                         secret_key: str, endpoint_url: str | None = None) -> None:
                ...  # build an aioboto3/boto3 client

            async def save(self, file_bytes: bytes, key: str) -> str:
                ...  # PutObject, return "s3://bucket/key" or the public URL

            async def delete(self, key: str) -> None:
                ...  # DeleteObject

            def get_path(self, key: str) -> Path:
                ...  # not meaningful for S3; download endpoint would instead
                     # redirect to a presigned GET URL rather than call this

        It would read AWS_S3_BUCKET, AWS_REGION, AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY (or rely on the default boto3 credential
        chain / IAM role) from `config.settings.settings`, and this
        factory would become:

            if settings.STORAGE_BACKEND == "s3":
                return S3StorageBackend(bucket=settings.AWS_S3_BUCKET, ...)
            return LocalStorageBackend()

    Everything that consumes `StorageBackend` (document_service.py, the
    files router) only depends on the `Protocol`, so no other file needs
    to change.
    """
    return LocalStorageBackend()
