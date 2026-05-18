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

import html
import shutil
import uuid
import zipfile
from xml.etree import ElementTree as ET
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
                "Allowed types: PDF, DOCX, Excel (.xlsx/.xls), JPG, PNG"
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


def build_variant_storage_path(
    category_id: int,
    directory_id: int,
    owner_user_id: int,
    variant_id: int,
    source_file_name: str,
) -> str:
    storage_root = Path(settings.STORAGE_ROOT)
    safe_name = Path(source_file_name or "variant").name
    relative = Path(str(category_id)) / str(directory_id) / "_variants" / str(owner_user_id) / str(variant_id) / safe_name
    abs_dir = storage_root / relative.parent
    abs_dir.mkdir(parents=True, exist_ok=True)
    return str(relative)


def copy_into_storage(source_relative_path: str, dest_relative_path: str) -> int:
    storage_root = Path(settings.STORAGE_ROOT)
    source_path = resolve_storage_path(source_relative_path)
    dest_path = (storage_root / dest_relative_path).resolve()

    if not str(dest_path).startswith(str(storage_root.resolve())):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest_path)
    return dest_path.stat().st_size


def extract_docx_preview_html(abs_path: Path) -> str:
    """
    Render a lightweight HTML preview from a DOCX file.

    This intentionally extracts plain paragraph text only. The frontend uses
    it as a stable DOM surface for sticky-note anchors.
    """

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    try:
        with zipfile.ZipFile(abs_path) as archive:
            xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, FileNotFoundError, ET.ParseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="DOCX preview is unavailable for this file",
        ) from exc

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="DOCX preview is unavailable for this file",
        ) from exc
    paragraphs: list[str] = []

    for index, paragraph in enumerate(root.findall(".//w:p", ns)):
        texts: list[str] = []
        for node in paragraph.findall(".//w:t", ns):
            if node.text:
                texts.append(node.text)
        content = html.escape("".join(texts)).strip()
        paragraphs.append(
            f'<p class="docx-paragraph" data-paragraph-index="{index}">{content or "&nbsp;"}</p>'
        )

    body = "".join(paragraphs) or "<p class=\"docx-paragraph\" data-paragraph-index=\"0\">&nbsp;</p>"
    return (
        '<div class="docx-preview-root" data-docx-preview="true">'
        f"{body}"
        "</div>"
    )


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
