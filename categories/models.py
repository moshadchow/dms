from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class CategoryBase(SQLModel):
    name:        str           = Field(unique=True, index=True, max_length=150)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active:   bool          = Field(default=True)


class Category(CategoryBase, table=True):
    """
    Top-level classification for documents (e.g. HR, Finance, Legal).
    Admin creates and manages categories; directories are created under a category.
    """

    __tablename__ = "categories"

    id:         Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime      = Field(default_factory=datetime.utcnow)
    updated_at: datetime      = Field(default_factory=datetime.utcnow)

    # Relationships
    directories: List["Directory"] = Relationship(back_populates="category")


# ── Pydantic schemas ──────────────────────────

class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(SQLModel):
    name:        Optional[str]  = None
    description: Optional[str]  = None
    is_active:   Optional[bool] = None


class CategoryRead(CategoryBase):
    id:         int
    created_at: datetime
    updated_at: datetime


class CategoryReadWithStats(CategoryRead):
    """Category with directory and document counts."""
    directory_count: int = 0
    document_count:  int = 0
