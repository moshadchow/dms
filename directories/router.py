from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from core.database import get_session
from core.dependencies import CurrentUser, require_permission
from directories.models import (
    DirectoryCreate,
    DirectoryNode,
    DirectoryRead,
    DirectoryReadWithDocCount,
    DirectoryUpdate,
)
from directories.service import DirectoryService
from users.models import PermissionAction

router = APIRouter()


@router.get(
    "/category/{category_id}",
    response_model=List[DirectoryRead],
    summary="List root directories for a category",
)
def list_directories(
    category_id: int,
    current_user: CurrentUser,
    session: Session = Depends(get_session),
):
    """Returns only top-level (root) directories. Use /tree for the full hierarchy."""
    return DirectoryService(session).list_by_category(category_id)


@router.get(
    "/category/{category_id}/tree",
    response_model=List[DirectoryNode],
    summary="Full nested directory tree for a category",
)
def get_tree(
    category_id:  int,
    current_user: CurrentUser,
    session:      Session = Depends(get_session),
):
    """
    Returns the complete recursive directory tree.
    Each node includes its children, enabling the frontend to render a collapsible tree.
    """
    return DirectoryService(session).get_tree(category_id)


@router.post(
    "",
    response_model=DirectoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create directory or subdirectory",
    dependencies=[Depends(require_permission(PermissionAction.CREATE))],
)
def create_directory(
    payload:      DirectoryCreate,
    current_user: CurrentUser,
    session:      Session = Depends(get_session),
):
    """
    Create a directory (or subdirectory by setting parent_id).
    Requires CREATE permission.
    """
    return DirectoryService(session).create_directory(payload, created_by=current_user.id)


@router.get("/{directory_id}", response_model=DirectoryRead, summary="Get directory by ID")
def get_directory(
    directory_id: int,
    current_user: CurrentUser,
    session:      Session = Depends(get_session),
):
    return DirectoryService(session).get_directory(directory_id)


@router.patch(
    "/{directory_id}",
    response_model=DirectoryRead,
    summary="Rename or update directory",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def update_directory(
    directory_id: int,
    payload:      DirectoryUpdate,
    current_user: CurrentUser,
    session:      Session = Depends(get_session),
):
    return DirectoryService(session).update_directory(directory_id, payload)


@router.delete(
    "/{directory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete directory (must be empty)",
    dependencies=[Depends(require_permission(PermissionAction.DELETE))],
)
def delete_directory(
    directory_id: int,
    current_user: CurrentUser,
    session:      Session = Depends(get_session),
):
    """Directory must have no subdirectories and no active documents."""
    DirectoryService(session).delete_directory(directory_id)
