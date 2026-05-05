from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class DirectoryBase(SQLModel):
    name:        str           = Field(max_length=255, index=True)
    description: Optional[str] = Field(default=None, max_length=500)


class Directory(DirectoryBase, table=True):
    """
    Hierarchical folder node.

    Tree structure
    ──────────────
    Category
    └── Directory          (parent_id = NULL  →  root of category)
        └── Subdirectory   (parent_id = Directory.id)
            └── ...        (unlimited nesting depth)

    Self-referencing via parent_id enables dynamic nested subdirectories.
    """

    __tablename__ = "directories"

    id:          Optional[int] = Field(default=None, primary_key=True)
    category_id: int           = Field(foreign_key="categories.id", index=True)
    parent_id:   Optional[int] = Field(default=None, foreign_key="directories.id", index=True)
    created_by:  int           = Field(foreign_key="users.id")
    created_at:  datetime      = Field(default_factory=datetime.utcnow)
    updated_at:  datetime      = Field(default_factory=datetime.utcnow)

    # ── Relationships ─────────────────────────
    # Plain string forward-refs — no Optional[] wrapper on Relationship().
    # SQLModel resolves these by class name at mapper init time.

    category: "Category" = Relationship(back_populates="directories")  # type: ignore[assignment]

    # Self-referencing children — queried explicitly in service layer
    children: List["Directory"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "Directory.id == foreign(Directory.parent_id)",
            "lazy": "selectin",
        }
    )

    # Creator user — no back_populates needed on User side
    created_by_user: "User" = Relationship(  # type: ignore[assignment]
        sa_relationship_kwargs={
            "lazy": "selectin",
            "foreign_keys": "[Directory.created_by]",
        }
    )

    # Documents housed in this directory
    documents: List["Document"] = Relationship(back_populates="directory")


# ── Pydantic schemas ──────────────────────────

class DirectoryCreate(DirectoryBase):
    category_id: int
    parent_id:   Optional[int] = None


class DirectoryUpdate(SQLModel):
    name:        Optional[str] = None
    description: Optional[str] = None


class DirectoryRead(DirectoryBase):
    id:          int
    category_id: int
    parent_id:   Optional[int]
    created_by:  int
    created_at:  datetime
    updated_at:  datetime

    model_config = {"from_attributes": True}


class DirectoryNode(DirectoryRead):
    """Recursive tree node — children are fully populated DirectoryNodes."""
    children: List["DirectoryNode"] = []

    model_config = {"from_attributes": True}


DirectoryNode.model_rebuild()


class DirectoryReadWithDocCount(DirectoryRead):
    """Directory with document count for dashboard display."""
    document_count: int = 0
    children_count: int = 0