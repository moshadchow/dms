from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from categories.models import CategoryCreate, CategoryRead, CategoryReadWithStats, CategoryUpdate
from categories.service import CategoryService
from core.database import get_session
from core.dependencies import AdminUser, CurrentUser

router = APIRouter()


@router.get("", response_model=List[CategoryReadWithStats], summary="List categories")
def list_categories(
    include_inactive: bool        = Query(False),
    current_user:     CurrentUser = None,
    session:          Session     = Depends(get_session),
):
    """Return all active categories with directory and document counts."""
    return CategoryService(session).list_categories(current_user, include_inactive)


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create category (Admin only)",
)
def create_category(
    payload: CategoryCreate,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return CategoryService(session).create_category(payload)


@router.get("/{category_id}", response_model=CategoryRead, summary="Get category by ID")
def get_category(
    category_id: int,
    current_user: CurrentUser = None,
    session:     Session     = Depends(get_session),
):
    return CategoryService(session).get_category(category_id, current_user)


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Update category (Admin only)",
)
def update_category(
    category_id: int,
    payload:     CategoryUpdate,
    _:           AdminUser = None,
    session:     Session   = Depends(get_session),
):
    return CategoryService(session).update_category(category_id, payload)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete category (Admin only)",
)
def delete_category(
    category_id: int,
    _:           AdminUser = None,
    session:     Session   = Depends(get_session),
):
    CategoryService(session).delete_category(category_id)
