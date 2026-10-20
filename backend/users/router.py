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
from users.schemas import (
    AdminPasswordResetRequest,
    DirectoryAccessAddRequest,
    DirectoryAccessResponse,
    DirectoryAccessSetRequest,
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
    user_level_id: Optional[int] = Query(None, description="Filter by user level ID"),
    company_id: Optional[int] = Query(None, description="Filter by company (SUPERADMIN only)"),
    _:         AdminUser      = None,
    current_user: CurrentUser = None,
    session:   Session        = Depends(get_session),
):
    users, total = UserService(session).list_users(
        skip, limit, search, is_active, user_level_id,
        current_user=current_user,
        company_id=company_id,
    )
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
    current_user: AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).create_user(payload, current_user=current_user)


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
    current_user: AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserService(session).update_user(user_id, payload, current_user=current_user)


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


@router.post(
    "/{user_id}/reset-password",
    summary="Reset a user's password (Admin only)",
)
def reset_password(
    user_id: int,
    _:       AdminUser = None,
    current_user: CurrentUser = None,
    session: Session   = Depends(get_session),
):
    """Generate a random password, hash it, email it to the user, and flag for change."""
    UserService(session).reset_password(user_id, current_admin_id=current_user.id)
    return {"message": "Password has been reset and sent to the user's email"}


# ──────────────────────────────────────────────
# Directory access grants (subdirectory-level)
# ──────────────────────────────────────────────

@router.get(
    "/{user_id}/directory-access",
    response_model=DirectoryAccessResponse,
    summary="Get a user's category + directory access grants (Admin only)",
)
def get_directory_access(
    user_id: int,
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    return UserService(session).get_directory_access(user_id, current_user)


@router.put(
    "/{user_id}/directory-access",
    response_model=DirectoryAccessResponse,
    summary="Replace a user's directory access grants (Admin only)",
)
def set_directory_access(
    user_id: int,
    payload: DirectoryAccessSetRequest,
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    return UserService(session).set_directory_access(
        user_id, payload.directory_ids, current_user
    )


@router.post(
    "/{user_id}/directory-access",
    response_model=DirectoryAccessResponse,
    summary="Grant one directory to a user, idempotent (Admin only)",
)
def add_directory_access(
    user_id: int,
    payload: DirectoryAccessAddRequest,
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    return UserService(session).add_directory_access(
        user_id, payload.directory_id, current_user
    )


@router.delete(
    "/{user_id}/directory-access/{directory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke one directory grant from a user (Admin only)",
)
def remove_directory_access(
    user_id: int,
    directory_id: int,
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    UserService(session).remove_directory_access(user_id, directory_id, current_user)


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
