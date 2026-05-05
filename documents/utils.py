"""
documents/utils.py
──────────────────
File system helpers for document upload, retrieval, and deletion.

All functions that touch the file system live here so the service
layer stays free of I/O concerns and is easier to unit-test.

Security contract
─────────────────
- resolve_storage_path() guards against path-traversal attacks by
  verifying the resolved absolute path stays inside STORAGE_ROOT.
- Clients never receive a raw storage path; they use the /view and
  /download endpoints which call resolve_storage_path() internally.
"""

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from core.config import settings
from documents.models import ALLOWED_MIME_TYPES, MAX_FILE_SIZE_BYTES, FileType


# ──────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────

def validate_file(file: UploadFile) -> FileType:
    """
    Validate the uploaded file's MIME type against the allow-list.

    Returns the resolved FileType enum on success.
    Raises HTTP 422 for unsupported types.

    Size validation is deferred to save_upload() once the full
    byte stream has been read.
    """
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"File type '{mime}' is not supported. "
                "Allowed types: PDF, Excel (.xlsx/.xls), JPG, PNG"
            ),
        )
    return ALLOWED_MIME_TYPES[mime]


# ──────────────────────────────────────────────
# Save
# ──────────────────────────────────────────────

async def save_upload(
    file: UploadFile,
    category_id: int,
    directory_id: int,
) -> tuple[str, int]:
    """
    Persist an uploaded file to disk.

    Storage layout:
        <STORAGE_ROOT>/<category_id>/<directory_id>/<uuid>_<original_filename>

    Returns:
        (relative_storage_path, file_size_in_bytes)

    relative_storage_path is the path stored in the DB.
    It is relative to STORAGE_ROOT so the app stays portable
    across deployments regardless of the absolute mount point.
    """
    storage_root = Path(settings.STORAGE_ROOT)
    dest_dir = storage_root / str(category_id) / str(directory_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'upload').name}"
    dest_path = dest_dir / safe_name

    content = await file.read()

    # Enforce size limit after reading the full stream
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the {settings.MAX_FILE_SIZE_MB} MB limit",
        )

    dest_path.write_bytes(content)

    relative = str(dest_path.relative_to(storage_root))
    return relative, len(content)


# ──────────────────────────────────────────────
# Resolve
# ──────────────────────────────────────────────

def resolve_storage_path(relative_path: str) -> Path:
    """
    Convert a relative DB storage path to a validated absolute Path.

    Raises HTTP 400 if the resolved path escapes STORAGE_ROOT
    (path-traversal guard).
    Raises HTTP 404 if the file does not exist on disk.
    """
    storage_root = Path(settings.STORAGE_ROOT).resolve()
    abs_path = (storage_root / relative_path).resolve()

    # Path-traversal guard
    if not str(abs_path).startswith(str(storage_root)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path",
        )

    if not abs_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk",
        )

    return abs_path


# ──────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────

def delete_from_disk(relative_path: str) -> None:
    """
    Permanently remove a stored file from disk.

    Silently ignores the case where the file is already missing —
    this makes hard-delete idempotent and safe to retry.
    """
    try:
        path = resolve_storage_path(relative_path)
        path.unlink(missing_ok=True)
    except HTTPException:
        # File not found or path invalid — nothing to delete
        pass