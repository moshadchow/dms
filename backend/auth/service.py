from datetime import datetime, timedelta
import jwt
from sqlmodel import Session, select
from typing import Optional

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from core.config import settings
from core.exceptions import InvalidCredentialsError, InactiveAccountError
from core.security import (
    create_token_pair,
    hash_password,
    verify_password,
    verify_refresh_token,
    TokenPair,
)
from users.models import User, CompanyRead
from company_profile.models import Company
from auth.schemas import CompanyOption, LoginResponse


class AuthService:
    def __init__(self, session: Session):
        self.session = session

    def _selection_token(self, user_ids: list[int]) -> str:
        expire = datetime.utcnow() + timedelta(minutes=5)
        payload = {
            "sub": "company_selection",
            "type": "company_selection",
            "uids": user_ids,
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def _verify_selection_token(self, token: str) -> list[int]:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "company_selection":
            raise ValueError("invalid token type")
        return list(payload.get("uids", []))

    def login(self, email: str, password: str, company_id: Optional[int] = None) -> LoginResponse:
        users = self.session.exec(select(User).where(User.email == email)).all()
        valid = [
            u for u in users
            if u.is_active and u.hashed_password and verify_password(password, u.hashed_password)
        ]
        if not valid:
            AuditService(self.session).log_event(
                action=AuditAction.FAILED_LOGIN,
                module=AuditModule.AUTH,
                description=f"Failed login attempt for {email}",
                is_success=False,
                failure_reason="Invalid credentials",
            )
            raise InvalidCredentialsError()

        if company_id is not None:
            chosen = [u for u in valid if u.company_id == company_id]
            if not chosen:
                raise InvalidCredentialsError()
            user = chosen[0]
            tp = create_token_pair(user.id)
            AuditService(self.session).log_event(
                action=AuditAction.LOGIN,
                module=AuditModule.AUTH,
                company_id=user.company_id,
                entity_name="user",
                entity_id=str(user.id),
                description=f"Local login successful for {email}",
                is_success=True,
                user=user,
            )
            return LoginResponse(access_token=tp.access_token, refresh_token=tp.refresh_token)

        if len(valid) == 1:
            user = valid[0]
            tp = create_token_pair(user.id)
            AuditService(self.session).log_event(
                action=AuditAction.LOGIN,
                module=AuditModule.AUTH,
                company_id=user.company_id,
                entity_name="user",
                entity_id=str(user.id),
                description=f"Local login successful for {email}",
                is_success=True,
                user=user,
            )
            return LoginResponse(access_token=tp.access_token, refresh_token=tp.refresh_token)

        token = self._selection_token([u.id for u in valid])
        companies = []
        for u in valid:
            company = self.session.get(Company, u.company_id) if u.company_id else None
            companies.append(CompanyOption(id=u.company_id, name=company.full_name if company else "Unknown"))
        return LoginResponse(
            requires_company_selection=True,
            selection_token=token,
            companies=companies,
        )

    def select_company(self, selection_token: str, company_id: int) -> LoginResponse:
        try:
            uids = self._verify_selection_token(selection_token)
        except Exception:
            raise InvalidCredentialsError()
        user = None
        for uid in uids:
            candidate = self.session.get(User, uid)
            if candidate and candidate.company_id == company_id and candidate.is_active:
                user = candidate
                break
        if user is None:
            raise InvalidCredentialsError()
        tp = create_token_pair(user.id)
        AuditService(self.session).log_event(
            action=AuditAction.LOGIN,
            module=AuditModule.AUTH,
            company_id=user.company_id,
            entity_name="user",
            entity_id=str(user.id),
            description=f"Company selected login for {user.email}",
            is_success=True,
            user=user,
        )
        return LoginResponse(access_token=tp.access_token, refresh_token=tp.refresh_token)

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

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        from fastapi import HTTPException, status

        if user.must_change_password:
            pass
        elif not user.hashed_password or not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        user.hashed_password = hash_password(new_password)
        user.must_change_password = False
        self.session.add(user)
        self.session.commit()

        AuditService(self.session).log_event(
            action=AuditAction.PASSWORD_CHANGED,
            module=AuditModule.AUTH,
            company_id=user.company_id,
            entity_name="user",
            entity_id=str(user.id),
            description="Password changed successfully",
            is_success=True,
            user=user,
        )
