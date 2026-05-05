from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from users.models import UserReadShort


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class FileType(str, Enum):
    PDF   = "pdf"
    EXCEL = "excel"   # .xlsx / .xls
    IMAGE = "image"   # .jpg / .jpeg / .png


class DocumentStatus(str, Enum):
    ACTIVE   = "active"    # visible to all permitted roles
    ARCHIVED = "archived"  # hidden from default listings; admin can restore
    DELETED  = "deleted"   # soft-deleted; excluded from all listings


# ──────────────────────────────────────────────
# Allowed MIME type ↔ FileType mapping
# ──────────────────────────────────────────────

ALLOWED_MIME_TYPES: dict[str, FileType] = {
    "application/pdf":                                                   FileType.PDF,
    "application/vnd.ms-excel":                                          FileType.EXCEL,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.EXCEL,
    "image/jpeg":                                                        FileType.IMAGE,
    "image/png":                                                         FileType.IMAGE,
}

MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB hard limit


# ──────────────────────────────────────────────
# Document Model
# ──────────────────────────────────────────────

class DocumentBase(SQLModel):
    title:       str           = Field(max_length=255, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)


class Document(DocumentBase, table=True):
    """
    Represents an uploaded file stored in the system.

    The `storage_path` column holds the server-side relative path.
    Clients never receive it — they use /view and /download endpoints.
    """

    __tablename__ = "documents"

    id:           Optional[int] = Field(default=None, primary_key=True)
    directory_id: int           = Field(foreign_key="directories.id", index=True)
    uploaded_by:  int           = Field(foreign_key="users.id")

    # File metadata
    file_name:    str           = Field(max_length=255)
    file_type:    FileType      = Field(index=True)
    mime_type:    str           = Field(max_length=127)
    file_size:    int           = Field(ge=0)
    storage_path: str           = Field(max_length=512)   # never sent to client

    # Lifecycle
    status:     DocumentStatus = Field(default=DocumentStatus.ACTIVE, index=True)
    created_at: datetime       = Field(default_factory=datetime.utcnow)
    updated_at: datetime       = Field(default_factory=datetime.utcnow)

    # ── Relationships ─────────────────────────
    # Use plain string forward-references (no Optional wrapper on Relationship).
    # SQLModel resolves these by table name at mapper init time.

    directory:        "Directory" = Relationship(back_populates="documents")  # type: ignore[assignment]
    uploaded_by_user: "User"      = Relationship(                             # type: ignore[assignment]
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Document.uploaded_by]"}
    )


# ── Pydantic schemas ──────────────────────────

class DocumentCreate(DocumentBase):
    """Built internally after file is saved to disk — never sent by client."""
    directory_id: int
    file_name:    str
    file_type:    FileType
    mime_type:    str
    file_size:    int
    storage_path: str


class DocumentUpdate(SQLModel):
    title:       Optional[str]            = None
    description: Optional[str]            = None
    status:      Optional[DocumentStatus] = None


class DocumentRead(DocumentBase):
    """Safe read schema — storage_path intentionally excluded."""
    id:           int
    directory_id: int
    uploaded_by:  int
    file_name:    str
    file_type:    FileType
    mime_type:    str
    file_size:    int
    status:       DocumentStatus
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}


class DocumentReadWithUploader(DocumentRead):
    """Document with uploader info — used in directory listings."""
    uploader: Optional["UserReadShort"] = None


class DocumentListResponse(SQLModel):
    """Paginated document list."""
    total: int
    page:  int
    limit: int
    items: List[DocumentRead]