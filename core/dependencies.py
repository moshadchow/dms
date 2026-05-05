from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlmodel import Session

from core.database import get_session
from core.security import verify_access_token
from users.models import PermissionAction, User, get_user_with_roles


class OptionalHTTPBearer(HTTPBearer):
    async def __call__(
        self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        try:
            return await super().__call__(request)
        except HTTPException:
            return None


bearer_scheme = OptionalHTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session:     Session                                = Depends(get_session),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials or not credentials.credentials:
        raise credentials_exc

    try:
        payload  = verify_access_token(credentials.credentials)
        user_id  = int(payload.sub)
    except (JWTError, ValueError):
        raise credentials_exc

    # Use selectinload to fetch user + roles + permissions in one go
    # so all data is in memory before the session closes.
    user = get_user_with_roles(session, user_id)
    if not user:
        raise credentials_exc
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DBSession   = Annotated[Session, Depends(get_session)]


def require_permission(action: PermissionAction):
    def _guard(current_user: CurrentUser) -> User:
        if current_user.is_admin():
            return current_user
        if not current_user.has_permission(action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{action.value}' action required",
            )
        return current_user
    return _guard


def require_admin(current_user: CurrentUser) -> User:
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]