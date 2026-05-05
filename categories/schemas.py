"""
categories/schemas.py
─────────────────────
Pydantic request / response schemas for the Categories endpoints.

Categories are the top-level classifiers in the DMS hierarchy:
    Category → Directory → Subdirectory → Document

Only Admins may create / update / delete categories.
All authenticated users may list and view categories.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════
# Create
# ══════════════════════════════════════════════

class CategoryCreateRequest(BaseModel):
    """
    Body for POST /categories — Admin only.

    name        Unique, human-readable label (e.g. "Human Resources", "Finance").
    description Optional context shown in the UI.
    is_active   Inactive categories are hidden from non-admin users.
    """

    name:        str           = Field(
                                    ...,
                                    min_length=2,
                                    max_length=150,
                                    examples=["Human Resources"],
                                )
    description: Optional[str] = Field(None, max_length=500)
    is_active:   bool          = Field(True)


# ══════════════════════════════════════════════
# Update
# ══════════════════════════════════════════════

class CategoryUpdateRequest(BaseModel):
    """
    Body for PATCH /categories/{category_id} — Admin only.
    All fields optional; only supplied fields are applied.
    """

    name:        Optional[str]  = Field(None, min_length=2, max_length=150)
    description: Optional[str]  = Field(None, max_length=500)
    is_active:   Optional[bool] = None


# ══════════════════════════════════════════════
# Responses
# ══════════════════════════════════════════════

class CategoryResponse(BaseModel):
    """Base category detail — returned on create / get / update."""

    id:          int
    name:        str
    description: Optional[str]
    is_active:   bool
    created_at:  datetime
    updated_at:  datetime

    model_config = {"from_attributes": True}


class CategoryStatsResponse(CategoryResponse):
    """
    Category with aggregated counts — returned by GET /categories.
    Used by the dashboard to display at-a-glance statistics.
    """

    directory_count: int = Field(0, description="Total directories under this category")
    document_count:  int = Field(0, description="Total active documents under this category")


class CategoryShortResponse(BaseModel):
    """Minimal projection embedded inside directory responses."""

    id:   int
    name: str

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# List
# ══════════════════════════════════════════════

class CategoryListResponse(BaseModel):
    """Response envelope for GET /categories."""

    total: int
    items: List[CategoryStatsResponse]


# ══════════════════════════════════════════════
# Bulk actions (Admin)
# ══════════════════════════════════════════════

class CategoryToggleRequest(BaseModel):
    """
    Body for POST /categories/{category_id}/toggle-active.
    Convenience endpoint to flip the is_active flag without a full PATCH.
    """

    is_active: bool


class CategoryDeleteResponse(BaseModel):
    """Confirmation body returned after a successful delete."""

    detail:      str
    category_id: int
