from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from core.database import get_session
from core.dependencies import AdminUser, CurrentUser
from user_levels.models import UserLevelCreate, UserLevelRead, UserLevelUpdate
from user_levels.service import UserLevelService

router = APIRouter()


@router.get("", response_model=List[UserLevelRead], summary="List all user levels")
def list_user_levels(
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserLevelService(session).list_user_levels()


@router.get("/active", response_model=List[UserLevelRead], summary="List active user levels")
def list_active_user_levels(
    _:       CurrentUser = None,
    session: Session     = Depends(get_session),
):
    return UserLevelService(session).list_active_user_levels()


@router.post(
    "",
    response_model=UserLevelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user level (Admin only)",
)
def create_user_level(
    payload: UserLevelCreate,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return UserLevelService(session).create_user_level(payload)


@router.get("/{level_id}", response_model=UserLevelRead, summary="Get user level by ID")
def get_user_level(
    level_id: int,
    _:        AdminUser = None,
    session:  Session   = Depends(get_session),
):
    return UserLevelService(session).get_user_level(level_id)


@router.patch(
    "/{level_id}",
    response_model=UserLevelRead,
    summary="Update user level (Admin only)",
)
def update_user_level(
    level_id: int,
    payload:  UserLevelUpdate,
    _:        AdminUser = None,
    session:  Session   = Depends(get_session),
):
    return UserLevelService(session).update_user_level(level_id, payload)


@router.delete(
    "/{level_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user level (Admin only)",
)
def delete_user_level(
    level_id: int,
    _:        AdminUser = None,
    session:  Session   = Depends(get_session),
):
    UserLevelService(session).delete_user_level(level_id)
