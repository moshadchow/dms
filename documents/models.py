from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from users.models import UserReadShort


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    EXCEL = "excel"
    IMAGE = "image"


class DocumentStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class DocumentVariantType(str, Enum):
    PRIVATE_ANNOTATION = "private_annotation"


class DocumentVariantStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class AnnotationAnchorType(str, Enum):
    POINT = "point"
    TEXT_RANGE = "text_range"


ALLOWED_MIME_TYPES: dict[str, FileType] = {
    "application/pdf": FileType.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
    "application/vnd.ms-excel": FileType.EXCEL,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.EXCEL,
    "image/jpeg": FileType.IMAGE,
    "image/png": FileType.IMAGE,
}

MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024


class DocumentBase(SQLModel):
    title: str = Field(max_length=255, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)


class Document(DocumentBase, table=True):
    __tablename__ = "documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    directory_id: int = Field(foreign_key="directories.id", index=True)
    uploaded_by: int = Field(foreign_key="users.id")

    file_name: str = Field(max_length=255)
    file_type: FileType = Field(index=True)
    mime_type: str = Field(max_length=127)
    file_size: int = Field(ge=0)
    storage_path: str = Field(max_length=512)

    status: DocumentStatus = Field(default=DocumentStatus.ACTIVE, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    directory: "Directory" = Relationship(back_populates="documents")  # type: ignore[assignment]
    uploaded_by_user: "User" = Relationship(  # type: ignore[assignment]
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Document.uploaded_by]"}
    )
    variants: List["DocumentVariant"] = Relationship(  # type: ignore[assignment]
        back_populates="source_document",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class DocumentVariant(SQLModel, table=True):
    __tablename__ = "document_variants"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_document_id: int = Field(foreign_key="documents.id", index=True)
    owner_user_id: int = Field(foreign_key="users.id", index=True)
    category_id: int = Field(foreign_key="categories.id", index=True)
    directory_id: int = Field(foreign_key="directories.id", index=True)

    variant_type: DocumentVariantType = Field(
        default=DocumentVariantType.PRIVATE_ANNOTATION,
        index=True,
    )
    status: DocumentVariantStatus = Field(
        default=DocumentVariantStatus.ACTIVE,
        index=True,
    )

    title: str = Field(max_length=255)
    source_file_name: str = Field(max_length=255)
    source_mime_type: str = Field(max_length=127)
    file_type: FileType = Field(index=True)
    file_size: int = Field(ge=0)
    storage_path: str = Field(max_length=512)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    source_document: Document = Relationship(  # type: ignore[assignment]
        back_populates="variants",
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[DocumentVariant.source_document_id]"},
    )
    owner_user: "User" = Relationship(  # type: ignore[assignment]
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[DocumentVariant.owner_user_id]"},
    )
    annotations: List["DocumentAnnotation"] = Relationship(  # type: ignore[assignment]
        back_populates="variant",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )


class DocumentAnnotation(SQLModel, table=True):
    __tablename__ = "document_annotations"

    id: Optional[int] = Field(default=None, primary_key=True)
    variant_id: int = Field(foreign_key="document_variants.id", index=True)
    page_number: Optional[int] = Field(default=None, index=True)
    anchor_type: AnnotationAnchorType = Field(index=True)
    anchor_data: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    note_text: str = Field(max_length=5000)
    color: str = Field(default="#f59e0b", max_length=32)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    variant: DocumentVariant = Relationship(  # type: ignore[assignment]
        back_populates="annotations",
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[DocumentAnnotation.variant_id]"},
    )


class DocumentCreate(DocumentBase):
    directory_id: int
    file_name: str
    file_type: FileType
    mime_type: str
    file_size: int
    storage_path: str


class DocumentUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[DocumentStatus] = None


class DocumentRead(DocumentBase):
    id: int
    directory_id: int
    uploaded_by: int
    file_name: str
    file_type: FileType
    mime_type: str
    file_size: int
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @property
    def file_size_human(self) -> str:
        size = float(self.file_size)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class DocumentReadWithUploader(DocumentRead):
    uploader: Optional["UserReadShort"] = None


class DocumentListResponse(SQLModel):
    total: int
    page: int
    limit: int
    items: List[DocumentRead]


class DocumentAnnotationCreate(SQLModel):
    page_number: Optional[int] = None
    anchor_type: AnnotationAnchorType
    anchor_data: Dict[str, Any] = Field(default_factory=dict)
    note_text: str = Field(min_length=1, max_length=5000)
    color: str = Field(default="#f59e0b", max_length=32)


class DocumentVariantSaveRequest(SQLModel):
    annotations: List[DocumentAnnotationCreate] = Field(default_factory=list)


class DocumentAnnotationRead(SQLModel):
    id: int
    variant_id: int
    page_number: Optional[int] = None
    anchor_type: AnnotationAnchorType
    anchor_data: Dict[str, Any]
    note_text: str
    color: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentVariantRead(SQLModel):
    id: int
    source_document_id: int
    owner_user_id: int
    category_id: int
    directory_id: int
    variant_type: DocumentVariantType
    status: DocumentVariantStatus
    title: str
    source_file_name: str
    source_mime_type: str
    file_type: FileType
    file_size: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentWorkspaceRead(SQLModel):
    document: DocumentRead
    variant: Optional[DocumentVariantRead] = None
    annotations: List[DocumentAnnotationRead] = Field(default_factory=list)
    preview_html: Optional[str] = None
    preview_error: Optional[str] = None
    has_private_variant: bool = False
