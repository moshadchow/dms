from sqlmodel import Session, select

from core.exceptions import InvalidCredentialsError, InactiveAccountError
from core.security import (
    create_token_pair,
    hash_password,
    verify_password,
    verify_refresh_token,
    TokenPair,
)
from users.models import User


class AuthService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Login
    # ──────────────────────────────────────────

    def login(self, email: str, password: str) -> TokenPair:
        user = self.session.exec(
            select(User).where(User.email == email)
        ).first()

        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveAccountError()

        return create_token_pair(user.id)

    # ──────────────────────────────────────────
    # Refresh
    # ──────────────────────────────────────────

    def refresh(self, refresh_token: str) -> TokenPair:
        from jose import JWTError
        from fastapi import HTTPException, status

        try:
            payload = verify_refresh_token(refresh_token)
            user_id = int(payload.sub)
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user = self.session.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        return create_token_pair(user.id)

    # ──────────────────────────────────────────
    # Password change
    # ──────────────────────────────────────────

    def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        from fastapi import HTTPException, status

        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        user.hashed_password = hash_password(new_password)
        self.session.add(user)
        self.session.commit()
