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

        if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
            # Log failed login attempt
            try:
                from audit.service import AuditService
                from audit.models import AuditAction, AuditModule
                svc = AuditService(self.session)
                svc.log_event(
                    action=AuditAction.FAILED_LOGIN,
                    module=AuditModule.AUTH,
                    entity_name="user",
                    entity_id=str(user.id) if user else None,
                    description=f"Failed login attempt for {email}",
                    is_success=False,
                    failure_reason="Invalid credentials",
                    user=user,
                )
            except Exception:
                pass
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveAccountError()

        # Log successful login
        try:
            from audit.service import AuditService
            from audit.models import AuditAction, AuditModule
            svc = AuditService(self.session)
            svc.log_event(
                action=AuditAction.LOGIN,
                module=AuditModule.AUTH,
                entity_name="user",
                entity_id=str(user.id),
                description=f"Local login successful for {email}",
                is_success=True,
                user=user,
            )
        except Exception:
            pass

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

        if not user.hashed_password or not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        user.hashed_password = hash_password(new_password)
        self.session.add(user)
        self.session.commit()

        # Log password change
        try:
            from audit.service import AuditService
            from audit.models import AuditAction, AuditModule
            svc = AuditService(self.session)
            svc.log_event(
                action=AuditAction.PASSWORD_CHANGED,
                module=AuditModule.AUTH,
                entity_name="user",
                entity_id=str(user.id),
                description="Password changed successfully",
                is_success=True,
                user=user,
            )
        except Exception:
            pass
