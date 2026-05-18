from fastapi import APIRouter, Depends
from sqlmodel import Session

from auth.schemas import LoginRequest, PasswordChangeRequest, RefreshRequest, TokenResponse
from auth.service import AuthService
from core.database import get_session
from core.dependencies import CurrentUser
from users.models import AssignedCategoryRead, PermissionRead, RoleRead, UserRead

router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="Obtain JWT token pair")
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
):
    """
    Authenticate with email + password.
    Returns an access token (1 h) and a refresh token (7 days).
    """
    token_pair = AuthService(session).login(payload.email, payload.password)
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse, summary="Rotate token pair")
def refresh(
    payload: RefreshRequest,
    session: Session = Depends(get_session),
):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    token_pair = AuthService(session).refresh(payload.refresh_token)
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
    )


@router.get("/me", response_model=UserRead, summary="Current user profile")
def me(current_user: CurrentUser):
    """
    Return the authenticated user's profile and assigned roles.
    Roles and permissions are already eagerly loaded by get_current_user
    so this serialises safely after the session closes.
    """
    # Build UserRead explicitly from already-loaded ORM data
    # to avoid any remaining lazy-load attempts during serialisation.
    return UserRead(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        roles=[
            RoleRead(
                id=role.id,
                name=role.name,
                description=role.description,
                created_at=role.created_at,
                permissions=[
                    PermissionRead(
                        id=perm.id,
                        action=perm.action,
                        description=perm.description,
                    )
                    for perm in role.permissions
                ],
            )
            for role in current_user.roles
        ],
        categories=[
            AssignedCategoryRead(
                id=category.id,
                name=category.name,
                description=category.description,
                is_active=category.is_active,
            )
            for category in current_user.categories
        ],
    )


@router.post("/change-password", summary="Change own password")
def change_password(
    payload:      PasswordChangeRequest,
    current_user: CurrentUser,
    session:      Session = Depends(get_session),
):
    """Allow any authenticated user to change their own password."""
    AuthService(session).change_password(
        current_user, payload.current_password, payload.new_password
    )
    return {"detail": "Password updated successfully"}
