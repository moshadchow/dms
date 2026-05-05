"""
documents/schemas.py
────────────────────
Pydantic request / response schemas for the Documents endpoints.

Security contract
─────────────────
storage_path is NEVER included in any response schema.
Clients access file content exclusively through:
  • GET /documents/{id}/view      → inline browser preview
  • GET /documents/{id}/download  → file download attachment

Upload flow
───────────
POST /documents/upload accepts multipart/form-data:
  • file         — the binary file (UploadFile)
  • title        — display name
  • description  — optional notes
  • directory_id — target directory

Lifecycle states
────────────────
  active   →  archive  →  active   (toggle via /archive and /restore)
  active   →  deleted              (soft delete — file kept on disk)
  deleted  →  active               (restore — Admin only)
  active   →  [hard delete]        (permanent — Admin only, removes disk file)
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from documents.models import DocumentStatus, FileType


# ══════════════════════════════════════════════
# Upload (multipart/form-data fields)
# ══════════════════════════════════════════════

class DocumentUploadForm(BaseModel):
    """
    Form fields submitted alongside the file binary in POST /documents/upload.
    FastAPI reads these from Form(...) parameters — this schema documents
    the expected shape and validates values after parsing.
    """

    title:        str           = Field(..., min_length=1, max_length=255,
                                        examples=["Q1 Financial Report"])
    description:  Optional[str] = Field(None, max_length=1000)
    directory_id: int           = Field(..., description="Target directory ID")


# ══════════════════════════════════════════════
# Update
# ══════════════════════════════════════════════

class DocumentUpdateRequest(BaseModel):
    """
    Body for PATCH /documents/{document_id}.
    Requires UPDATE permission.
    All fields optional — only provided values are changed.
    status should only be used by Admin to override lifecycle state.
    """

    title:       Optional[str]            = Field(None, min_length=1, max_length=255)
    description: Optional[str]            = Field(None, max_length=1000)
    status:      Optional[DocumentStatus] = Field(
                                               None,
                                               description="Admin override of document status",
                                           )

    @field_validator("status")
    @classmethod
    def disallow_deleted_via_patch(cls, v: Optional[DocumentStatus]):
        """Soft-delete must go through DELETE /documents/{id}, not PATCH."""
        if v == DocumentStatus.DELETED:
            raise ValueError(
                "Use DELETE /documents/{id} to soft-delete. "
                "PATCH cannot set status to 'deleted'."
            )
        return v


# ══════════════════════════════════════════════
# Uploader short projection (embedded in document responses)
# ══════════════════════════════════════════════

class UploaderShortResponse(BaseModel):
    """Lightweight user info embedded inside DocumentDetailResponse."""

    id:        int
    full_name: str
    email:     str

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# Document — Responses
# ══════════════════════════════════════════════

class DocumentResponse(BaseModel):
    """
    Safe document metadata returned to clients.

    storage_path is intentionally absent — it must never be exposed.
    Clients use /view and /download endpoints to access file content.
    """

    id:           int
    title:        str
    description:  Optional[str]
    directory_id: int
    uploaded_by:  int
    file_name:    str
    file_type:    FileType
    mime_type:    str
    file_size:    int           = Field(..., description="File size in bytes")
    status:       DocumentStatus
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}

    @property
    def file_size_human(self) -> str:
        """Human-readable file size (convenience — not serialised by default)."""
        for unit in ("B", "KB", "MB", "GB"):
            if self.file_size < 1024:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024
        return f"{self.file_size:.1f} TB"


class DocumentDetailResponse(DocumentResponse):
    """
    Extended document response with uploader info.
    Returned by GET /documents/{id} and POST /documents/upload.
    """

    uploader: Optional[UploaderShortResponse] = None


class DocumentCardResponse(BaseModel):
    """
    Compact projection for directory listing cards in the UI.
    Omits heavy fields (description, mime_type) to keep list payloads small.
    """

    id:         int
    title:      str
    file_name:  str
    file_type:  FileType
    file_size:  int
    uploaded_by: int
    status:     DocumentStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# Document — List / Search
# ══════════════════════════════════════════════

class DocumentListResponse(BaseModel):
    """
    Paginated document list returned by GET /documents.

    page is 1-based.  next_page / prev_page are null at boundaries.
    """

    total:     int
    page:      int
    limit:     int
    items:     List[DocumentResponse]
    next_page: Optional[int] = None
    prev_page: Optional[int] = None

    @classmethod
    def build(
        cls,
        items: List[DocumentResponse],
        total: int,
        skip: int,
        limit: int,
    ) -> "DocumentListResponse":
        page = skip // limit + 1
        return cls(
            total=total,
            page=page,
            limit=limit,
            items=items,
            next_page=page + 1 if skip + limit < total else None,
            prev_page=page - 1 if page > 1 else None,
        )


# ══════════════════════════════════════════════
# File type filter (used as query param schema)
# ══════════════════════════════════════════════

class DocumentFilterParams(BaseModel):
    """
    Query parameters accepted by GET /documents.
    Validated centrally so routers stay clean.
    """

    directory_id: Optional[int]      = None
    category_id:  Optional[int]      = None
    file_type:    Optional[FileType] = Field(None, description="pdf | excel | image")
    status:       Optional[DocumentStatus] = Field(
                                               DocumentStatus.ACTIVE,
                                               description="Defaults to active",
                                             )
    search:       Optional[str]      = Field(
                                           None,
                                           max_length=255,
                                           description="Search title or filename",
                                       )
    skip:         int = Field(0, ge=0)
    limit:        int = Field(50, ge=1, le=200)


# ══════════════════════════════════════════════
# Archive / Restore / Delete
# ══════════════════════════════════════════════

class DocumentStatusResponse(BaseModel):
    """
    Generic status-change confirmation.
    Returned by /archive, /restore, and DELETE endpoints.
    """

    detail:      str
    document_id: int
    status:      DocumentStatus


# ══════════════════════════════════════════════
# Upload progress / batch (future-ready)
# ══════════════════════════════════════════════

class BatchUploadResponse(BaseModel):
    """
    Returned when multiple files are uploaded in one request.
    (Placeholder — batch upload endpoint is a planned enhancement.)
    """

    total_uploaded: int
    succeeded:      List[DocumentResponse]
    failed:         List[dict]             = Field(
                                               default_factory=list,
                                               description="List of {filename, error} dicts",
                                           )
