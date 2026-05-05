import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from core.config import settings
from documents.models import ALLOWED_MIME_TYPES, MAX_FILE_SIZE_BYTES, FileType


def validate_file(file: UploadFile) -> FileType:
    """
    Validate content-type and file size.
    Returns the resolved FileType enum on success.
    Raises HTTP 422 for unsupported type, HTTP 413 for oversized files.
    """
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type '{mime}' is not supported. Allowed: PDF, Excel, JPG, PNG",
        )
    return ALLOWED_MIME_TYPES[mime]


async def save_upload(
    file: UploadFile,
    category_id: int,
    directory_id: int,
) -> tuple[str, int]:
    """
    Persist an uploaded file to disk under:
        storage/uploads/<category_id>/<directory_id>/<uuid>_<original_filename>

    Returns:
        (relative_storage_path, file_size_in_bytes)
    """
    storage_root = Path(settings.STORAGE_ROOT)
    dest_dir = storage_root / str(category_id) / str(directory_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'file').name}"
    dest_path = dest_dir / safe_name

    content = await file.read()

    # Size check (after read to get exact byte count)
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_FILE_SIZE_MB} MB limit",
        )

    dest_path.write_bytes(content)

    # Relative path stored in DB (never the absolute path)
    relative = str(dest_path.relative_to(storage_root))
    return relative, len(content)


def resolve_storage_path(relative_path: str) -> Path:
    """Return the absolute Path for a stored file, ensuring it exists."""
    storage_root = Path(settings.STORAGE_ROOT)
    abs_path = (storage_root / relative_path).resolve()

    # Security: prevent path traversal outside storage root
    if not str(abs_path).startswith(str(storage_root.resolve())):
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


def delete_from_disk(relative_path: str) -> None:
    """Remove a stored file from disk. Silently ignores missing files."""
    try:
        path = resolve_storage_path(relative_path)
        path.unlink(missing_ok=True)
    except HTTPException:
        pass
