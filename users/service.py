from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from categories.models import Category
from core.security import hash_password
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
    return UserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
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
    ) -> Tuple[List[UserRead], int]:
        query = select(User).options(
            selectinload(User.roles).selectinload(Role.permissions),  # type: ignore[arg-type]
            selectinload(User.categories),  # type: ignore[arg-type]
        )
        if search:
            query = query.where(
                User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
            )
        if is_active is not None:
            query = query.where(User.is_active == is_active)

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

        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hash_password(data.password),
            is_active=data.is_active,
        )
        self.session.add(user)
        self.session.flush()
        self._assign_roles(user.id, data.role_ids)
        self._assign_categories(user.id, data.category_ids)
        self.session.commit()

        # Re-fetch with eager load so roles are in memory
        return self.get_user(user.id)

    def update_user(self, user_id: int, data: UserUpdate) -> UserRead:
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

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

        user.updated_at = datetime.utcnow()
        self.session.add(user)
        self.session.commit()
        return self.get_user(user_id)

    def delete_user(self, user_id: int) -> None:
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        self.session.delete(user)
        self.session.commit()

    def deactivate_user(self, user_id: int) -> UserRead:
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        user.is_active = False
        user.updated_at = datetime.utcnow()
        self.session.add(user)
        self.session.commit()
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
        return self.get_role(role.id)

    # ──────────────────────────────────────────
    # Permissions
    # ──────────────────────────────────────────

    def list_permissions(self) -> List[PermissionRead]:
        perms = self.session.exec(select(Permission)).all()
        return [PermissionRead(id=p.id, action=p.action, description=p.description) for p in perms]
