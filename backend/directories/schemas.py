"""
directories/schemas.py
──────────────────────
Pydantic request / response schemas for the Directories endpoints.

Directory hierarchy
───────────────────
Category
└── Directory           (parent_id = NULL  →  root node)
    └── Subdirectory    (parent_id = Directory.id)
        └── ...         (unlimited depth)

Key design choices
──────────────────
- DirectoryNode is a recursive schema used to return the full
  category tree in a single API call (GET /directories/category/{id}/tree).
- DirectoryBreadcrumb supports building navigation breadcrumb paths.
- DirectoryMoveRequest supports moving a directory to a new parent.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════
# Create
# ══════════════════════════════════════════════

class DirectoryCreateRequest(BaseModel):
    """
    Body for POST /directories.
    Requires CREATE permission (Maker or Admin).

    parent_id   Omit (or pass null) to create a root-level directory.
                Provide an existing directory ID to create a subdirectory.
    """

    name:        str           = Field(
                                    ...,
                                    min_length=1,
                                    max_length=255,
                                    examples=["2024 Contracts"],
                                )
    description: Optional[str] = Field(None, max_length=500)
    category_id: int           = Field(..., description="Parent category ID")
    parent_id:   Optional[int] = Field(
                                    None,
                                    description="Parent directory ID — omit for root level",
                                )


# ══════════════════════════════════════════════
# Update
# ══════════════════════════════════════════════

class DirectoryUpdateRequest(BaseModel):
    """
    Body for PATCH /directories/{directory_id}.
    Requires UPDATE permission (Checker, Maker, or Admin).
    All fields optional.
    """

    name:        Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)


class DirectoryMoveRequest(BaseModel):
    """
    Body for POST /directories/{directory_id}/move.
    Moves a directory to a different parent within the same category.
    Requires UPDATE permission.

    new_parent_id   Pass null to promote the directory to root level.
    """

    new_parent_id: Optional[int] = Field(
        None,
        description="Target parent directory ID. Null = promote to root.",
    )


# ══════════════════════════════════════════════
# Responses — Flat
# ══════════════════════════════════════════════

class DirectoryResponse(BaseModel):
    """Flat directory detail — used in list and single-get responses."""

    id:          int
    name:        str
    description: Optional[str]
    category_id: int
    parent_id:   Optional[int]
    created_by:  int
    created_at:  datetime
    updated_at:  datetime

    model_config = {"from_attributes": True}


class DirectoryWithStatsResponse(DirectoryResponse):
    """
    Directory with counts — used in dashboard and sidebar panels.
    Includes immediate children count and total active documents.
    """

    children_count: int = Field(0, description="Number of immediate subdirectories")
    document_count: int = Field(0, description="Active documents in this directory")


# ══════════════════════════════════════════════
# Response — Recursive Tree Node
# ══════════════════════════════════════════════

class DirectoryNode(BaseModel):
    """
    Recursive tree node.

    Returned by GET /directories/category/{id}/tree.
    Each node carries its full children list so the frontend can
    render a collapsible directory tree without additional requests.

    Example JSON
    ────────────
    {
      "id": 1, "name": "HR", "children": [
        { "id": 3, "name": "Policies", "children": [] },
        { "id": 4, "name": "Contracts", "children": [
          { "id": 7, "name": "2024", "children": [] }
        ]}
      ]
    }
    """

    id:          int
    name:        str
    description: Optional[str]
    category_id: int
    parent_id:   Optional[int]
    created_by:  int
    created_at:  datetime
    updated_at:  datetime

    # Recursive children — populated by the directory service tree builder
    children:       List[DirectoryNode] = []
    document_count: int                 = 0

    model_config = {"from_attributes": True}


# Required for Pydantic v2 self-referential models
DirectoryNode.model_rebuild()


# ══════════════════════════════════════════════
# Response — Breadcrumb
# ══════════════════════════════════════════════

class DirectoryBreadcrumb(BaseModel):
    """Single step in a breadcrumb path (Category → Dir → Subdir → ...)."""

    id:   int
    name: str
    type: str = Field(
        ...,
        description="'category' | 'directory'",
        examples=["directory"],
    )


class DirectoryBreadcrumbResponse(BaseModel):
    """
    Ordered breadcrumb path from Category root to the target directory.
    Used by the frontend to render navigation context.

    Example:  Finance  →  2024  →  Q1 Reports
    """

    path: List[DirectoryBreadcrumb]


# ══════════════════════════════════════════════
# List
# ══════════════════════════════════════════════

class DirectoryListResponse(BaseModel):
    """Response envelope for GET /directories/category/{id} (flat root list)."""

    category_id: int
    total:       int
    items:       List[DirectoryWithStatsResponse]


# ══════════════════════════════════════════════
# Tree
# ══════════════════════════════════════════════

class DirectoryTreeResponse(BaseModel):
    """Response envelope for GET /directories/category/{id}/tree."""

    category_id: int
    tree:        List[DirectoryNode]
