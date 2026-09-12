from datetime import datetime
from typing import List, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel
from users.models import UserCategoryLink


class CategoryBase(SQLModel):
    name:        str           = Field(index=True, max_length=150)
    description: Optional[str] = Field(default=None, max_length=500)
    is_active:   bool          = Field(default=True)


class Category(CategoryBase, table=True):
    """
    Top-level classification for documents (e.g. HR, Finance, Legal).
    Admin creates and manages categories; directories are created under a category.
    Company-specific: each category belongs to exactly one company.
    """

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("name", "company_id", name="uq_category_name_company"),
    )

    id:         Optional[int] = Field(default=None, primary_key=True)
    company_id: int           = Field(foreign_key="companies.id", index=True)
    created_by: int           = Field(foreign_key="users.id", index=True)
    created_at: datetime      = Field(default_factory=datetime.utcnow)
    updated_at: datetime      = Field(default_factory=datetime.utcnow)

    # Relationships
    directories: List["Directory"] = Relationship(back_populates="category")
    users: List["User"] = Relationship(
        back_populates="categories",
        link_model=UserCategoryLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    company: Optional["Company"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    creator: Optional["User"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Category.created_by]"},
    )


# ── Pydantic schemas ──────────────────────────

class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(SQLModel):
    name:        Optional[str]  = None
    description: Optional[str]  = None
    is_active:   Optional[bool] = None


class CategoryRead(CategoryBase):
    id:         int
    company_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class CategoryReadWithStats(CategoryRead):
    """Category with directory and document counts."""
    directory_count: int = 0
    document_count:  int = 0
