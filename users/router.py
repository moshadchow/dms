from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from core.database import get_session
from core.dependencies import AdminUser, CurrentUser
from users.models import (
    PermissionRead,
    RoleCreate,
    RoleRead,
    UserCreate,
    UserRead,
    UserUpdate,
)
from users.service import UserService

router = APIRouter()


# ──────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────

@router.get("", response_model=dict, summary="List all users (Admin only)")
def list_users(
    skip:      int            = Query(0, ge=0),
    limit:     int            = Query(50, ge=1, le=200),
    search:    Optional[str]  = Query(None, description="Filter by name or email"),
    is_active: Optional[bool] = Query(None),
    _:         AdminUser      = None,
    session:   Session        = Depends(get_session),
):
    users, total = UserService(session).list_users(skip, limit, search, is_active)
    return {
        "total": total,
        "skip":  skip,
        "limit": limit,
        "items": [UserRead.model_validate(u) for u in users],
    }


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (Admin only)",
)
def create_user(
    payload: UserCreate,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).create_user(payload)


@router.get("/me", response_model=UserRead, summary="Current user's own profile")
def get_own_profile(current_user: CurrentUser):
    return current_user


@router.get("/{user_id}", response_model=UserRead, summary="Get user by ID (Admin only)")
def get_user(
    user_id: int,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).get_user(user_id)


@router.patch("/{user_id}", response_model=UserRead, summary="Update user (Admin only)")
def update_user(
    user_id: int,
    payload: UserUpdate,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).update_user(user_id, payload)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hard-delete user (Admin only)",
)
def delete_user(
    user_id: int,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    UserService(session).delete_user(user_id)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserRead,
    summary="Deactivate user account (Admin only)",
)
def deactivate_user(
    user_id: int,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).deactivate_user(user_id)


# ──────────────────────────────────────────────
# Roles
# ──────────────────────────────────────────────

@router.get("/roles/all", response_model=List[RoleRead], summary="List all roles")
def list_roles(
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).list_roles()


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom role (Admin only)",
)
def create_role(
    payload: RoleCreate,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).create_role(payload)


@router.get("/roles/{role_id}", response_model=RoleRead, summary="Get role by ID")
def get_role(
    role_id: int,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).get_role(role_id)


# ──────────────────────────────────────────────
# Permissions
# ──────────────────────────────────────────────

@router.get(
    "/permissions/all",
    response_model=List[PermissionRead],
    summary="List all permissions (Admin only)",
)
def list_permissions(
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).list_permissions()
