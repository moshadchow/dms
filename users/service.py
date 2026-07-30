from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from categories.models import Category
from core.security import hash_password
from user_levels.models import UserLevel, UserLevelRead
from users.models import (
    AssignedCategoryRead,
    Permission,
    PermissionAction,
    PermissionRead,
    Role,
    RoleCreate,
    RoleRead,
    RolePermissionLink,
    User,
    UserCategoryLink,
    UserCreate,
    UserRead,
    UserRoleLink,
    UserUpdate,
    get_user_with_roles,
)


def _role_to_read(role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        created_at=role.created_at,
        permissions=[
            PermissionRead(id=p.id, action=p.action, description=p.description)
            for p in role.permissions
        ],
    )


def _user_to_read(user: User) -> UserRead:
    level_read = None
    if user.user_level:
        level_read = UserLevelRead.model_validate(user.user_level)
    return UserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        auth_provider=user.auth_provider,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[_role_to_read(r) for r in user.roles],
        categories=[
            AssignedCategoryRead(
                id=category.id,
                name=category.name,
                description=category.description,
                is_active=category.is_active,
            )
            for category in user.categories
        ],
        user_level=level_read,
    )


class UserService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Users
    # ──────────────────────────────────────────

    def list_users(
        self,
        skip:      int = 0,
        limit:     int = 50,
        search:    Optional[str]  = None,
        is_active: Optional[bool] = None,
        user_level_id: Optional[int] = None,
    ) -> Tuple[List[UserRead], int]:
        query = select(User).options(
            selectinload(User.roles).selectinload(Role.permissions),  # type: ignore[arg-type]
            selectinload(User.categories),  # type: ignore[arg-type]
            selectinload(User.user_level),  # type: ignore[arg-type]
        )
        if search:
            query = query.where(
                User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
            )
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if user_level_id is not None:
            query = query.where(User.user_level_id == user_level_id)

        all_users = self.session.exec(query).all()
        total     = len(all_users)
        page      = self.session.exec(query.offset(skip).limit(limit)).all()
        return [_user_to_read(u) for u in page], total

    def get_user(self, user_id: int) -> UserRead:
        user = get_user_with_roles(self.session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        return _user_to_read(user)

    def create_user(self, data: UserCreate) -> UserRead:
        exists = self.session.exec(
            select(User).where(User.email == data.email)
        ).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{data.email}' is already registered",
            )

        # Determine user_level_id: use provided value, or default to "Low"
        level_id = data.user_level_id
        if level_id is None:
            default_level = self.session.exec(
                select(UserLevel).where(UserLevel.name == "Low", UserLevel.is_active == True)
            ).first()
            if default_level:
                level_id = default_level.id

        # Validate: local users must have a password
        auth_provider = data.auth_provider or "local"
        hashed_pw = None
        if auth_provider == "local":
            if not data.password:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Password is required for local users",
                )
            hashed_pw = hash_password(data.password)
        elif data.azure_object_id:
            hashed_pw = None

        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hashed_pw,
            is_active=data.is_active,
            user_level_id=level_id,
            auth_provider=auth_provider,
            azure_object_id=data.azure_object_id,
        )
        self.session.add(user)
        self.session.flush()
        self._assign_roles(user.id, data.role_ids)
        self._assign_categories(user.id, data.category_ids)
        self.session.commit()

        # Log audit event
        try:
            from audit.service import AuditService
            from audit.models import AuditAction, AuditModule
            svc = AuditService(self.session)
            svc.log_event(
                action=AuditAction.CREATE_USER,
                module=AuditModule.USERS,
                entity_name="user",
                entity_id=str(user.id),
                new_value={"email": data.email, "full_name": data.full_name},
                description=f"Created user {data.email}",
                is_success=True,
            )
        except Exception:
            pass

        # Re-fetch with eager load so roles are in memory
        return self.get_user(user.id)

    def update_user(self, user_id: int, data: UserUpdate) -> UserRead:
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        # Capture old values for audit
        old_values = {
            "full_name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
        }

        if data.full_name is not None:
            user.full_name = data.full_name
        if data.email is not None:
            dup = self.session.exec(
                select(User).where(User.email == data.email, User.id != user_id)
            ).first()
            if dup:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{data.email}' is already taken",
                )
            user.email = data.email
        if data.is_active is not None:
            user.is_active = data.is_active

        if data.role_ids is not None:
            for link in self.session.exec(
                select(UserRoleLink).where(UserRoleLink.user_id == user_id)
            ).all():
                self.session.delete(link)
            self.session.flush()
            self._assign_roles(user_id, data.role_ids)

        if data.category_ids is not None:
            for link in self.session.exec(
                select(UserCategoryLink).where(UserCategoryLink.user_id == user_id)
            ).all():
                self.session.delete(link)
            self.session.flush()
            self._assign_categories(user_id, data.category_ids)

        if data.user_level_id is not None or (hasattr(data, 'user_level_id') and 'user_level_id' in data.model_fields_set):
            user.user_level_id = data.user_level_id

        user.updated_at = datetime.utcnow()
        self.session.add(user)
        self.session.commit()

        # Log audit event
        try:
            from audit.service import AuditService
            from audit.models import AuditAction, AuditModule
            svc = AuditService(self.session)
            new_values = {
                "full_name": user.full_name,
                "email": user.email,
                "is_active": user.is_active,
            }
            svc.log_event(
                action=AuditAction.UPDATE_USER,
                module=AuditModule.USERS,
                entity_name="user",
                entity_id=str(user_id),
                old_value=old_values,
                new_value=new_values,
                description=f"Updated user {user.email}",
                is_success=True,
            )
        except Exception:
            pass

        return self.get_user(user_id)

    def delete_user(self, user_id: int) -> None:
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        email = user.email
        self.session.delete(user)
        self.session.commit()

        # Log audit event
        try:
            from audit.service import AuditService
            from audit.models import AuditAction, AuditModule
            svc = AuditService(self.session)
            svc.log_event(
                action=AuditAction.DELETE_USER,
                module=AuditModule.USERS,
                entity_name="user",
                entity_id=str(user_id),
                old_value={"email": email},
                description=f"Deleted user {email}",
                is_success=True,
            )
        except Exception:
            pass

    def deactivate_user(self, user_id: int) -> UserRead:
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        user.is_active = False
        user.updated_at = datetime.utcnow()
        self.session.add(user)
        self.session.commit()

        # Log audit event
        try:
            from audit.service import AuditService
            from audit.models import AuditAction, AuditModule
            svc = AuditService(self.session)
            svc.log_event(
                action=AuditAction.DEACTIVATE_USER,
                module=AuditModule.USERS,
                entity_name="user",
                entity_id=str(user_id),
                old_value={"is_active": True},
                new_value={"is_active": False},
                description=f"Deactivated user {user.email}",
                is_success=True,
            )
        except Exception:
            pass

        return self.get_user(user_id)

    def _assign_roles(self, user_id: int, role_ids: List[int]) -> None:
        for role_id in role_ids:
            role = self.session.get(Role, role_id)
            if not role:
                raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
            self.session.add(UserRoleLink(user_id=user_id, role_id=role_id))

    def _assign_categories(self, user_id: int, category_ids: List[int]) -> None:
        for category_id in category_ids:
            category = self.session.get(Category, category_id)
            if not category:
                raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
            self.session.add(UserCategoryLink(user_id=user_id, category_id=category_id))

    # ──────────────────────────────────────────
    # Roles
    # ──────────────────────────────────────────

    def list_roles(self) -> List[RoleRead]:
        roles = self.session.exec(
            select(Role).options(selectinload(Role.permissions))  # type: ignore[arg-type]
        ).all()
        return [_role_to_read(r) for r in roles]

    def get_role(self, role_id: int) -> RoleRead:
        role = self.session.exec(
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.permissions))  # type: ignore[arg-type]
        ).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
        return _role_to_read(role)

    def create_role(self, data: RoleCreate) -> RoleRead:
        exists = self.session.exec(
            select(Role).where(Role.name == data.name)
        ).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{data.name}' already exists",
            )
        role = Role(name=data.name, description=data.description)
        self.session.add(role)
        self.session.flush()
        for perm_id in data.permission_ids:
            perm = self.session.get(Permission, perm_id)
            if not perm:
                raise HTTPException(status_code=404, detail=f"Permission {perm_id} not found")
            self.session.add(RolePermissionLink(role_id=role.id, permission_id=perm_id))
        self.session.commit()

        # Log audit event
        try:
            from audit.service import AuditService
            from audit.models import AuditAction, AuditModule
            svc = AuditService(self.session)
            svc.log_event(
                action=AuditAction.CREATE_ROLE,
                module=AuditModule.USERS,
                entity_name="role",
                entity_id=str(role.id),
                new_value={"name": data.name.value if hasattr(data.name, "value") else str(data.name)},
                description=f"Created role {data.name}",
                is_success=True,
            )
        except Exception:
            pass

        return self.get_role(role.id)

    # ──────────────────────────────────────────
    # Permissions
    # ──────────────────────────────────────────

    def list_permissions(self) -> List[PermissionRead]:
        perms = self.session.exec(select(Permission)).all()
        return [PermissionRead(id=p.id, action=p.action, description=p.description) for p in perms]
