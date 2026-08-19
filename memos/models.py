from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from documents.models import Document
    from users.models import User
    from workflow.models import Signature


# ──────────────────────────────────────────────
# Link / Association Tables
# ──────────────────────────────────────────────

class MemoAttachment(SQLModel, table=True):
    __tablename__ = "memo_attachments"

    id: Optional[int] = Field(default=None, primary_key=True)
    memo_id: int = Field(foreign_key="memos.id", index=True, nullable=False)
    document_id: int = Field(foreign_key="documents.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    memo: "Memo" = Relationship(
        back_populates="attachments",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    document: "Document" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[MemoAttachment.document_id]"}
    )


# ──────────────────────────────────────────────
# Memo
# ──────────────────────────────────────────────

class MemoBase(SQLModel):
    memo_date: datetime = Field(default_factory=datetime.utcnow)
    subject: str = Field(max_length=255, index=True)
    body: str = Field(default="", max_length=50000)


class Memo(MemoBase, table=True):
    __tablename__ = "memos"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True, nullable=False, unique=True)
    author_signature_id: Optional[int] = Field(default=None, foreign_key="signatures.id")
    created_by: int = Field(foreign_key="users.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    document: "Document" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Memo.document_id]"}
    )
    author: "User" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Memo.created_by]"}
    )
    author_signature: Optional["Signature"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Memo.author_signature_id]"}
    )
    attachments: List[MemoAttachment] = Relationship(
        back_populates="memo",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )


# ──────────────────────────────────────────────
# Pydantic Read Schemas
# ──────────────────────────────────────────────

class MemoAttachmentRead(SQLModel):
    id: int
    memo_id: int
    document_id: int
    document_title: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class MemoRead(SQLModel):
    id: int
    document_id: int
    memo_date: datetime
    subject: str
    body: str
    author_signature_id: Optional[int] = None
    created_by: int
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    workflow_status: Optional[str] = None
    model_config = {"from_attributes": True}


class MemoDetailRead(MemoRead):
    directory_id: Optional[int] = None
    document_title: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    attachments: List[MemoAttachmentRead] = []
    user_level_ids: List[int] = []


class MemoListResponse(SQLModel):
    total: int
    page: int
    limit: int
    items: List[MemoRead]
