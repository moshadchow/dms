from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy.orm import selectinload
from sqlmodel import Field, Relationship, Session, SQLModel, select


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class RoleName(str, Enum):
    ADMIN   = "admin"
    MAKER   = "maker"
    CHECKER = "checker"
    AUDITOR = "auditor"


class PermissionAction(str, Enum):
    VIEW     = "view"
    DOWNLOAD = "download"
    CREATE   = "create"
    UPDATE   = "update"
    DELETE   = "delete"


# ──────────────────────────────────────────────
# Link / Association Tables
# ──────────────────────────────────────────────

class RolePermissionLink(SQLModel, table=True):
    __tablename__ = "role_permission_links"
    role_id:       Optional[int] = Field(default=None, foreign_key="roles.id",       primary_key=True)
    permission_id: Optional[int] = Field(default=None, foreign_key="permissions.id", primary_key=True)


class UserRoleLink(SQLModel, table=True):
    __tablename__ = "user_role_links"
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True)
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id", primary_key=True)


class UserCategoryLink(SQLModel, table=True):
    __tablename__ = "user_category_links"
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True)
    category_id: Optional[int] = Field(default=None, foreign_key="categories.id", primary_key=True)


# ──────────────────────────────────────────────
# Permission
# ──────────────────────────────────────────────

class PermissionBase(SQLModel):
    action:      PermissionAction = Field(index=True)
    description: Optional[str]   = Field(default=None, max_length=255)


class Permission(PermissionBase, table=True):
    __tablename__ = "permissions"
    id: Optional[int] = Field(default=None, primary_key=True)

    roles: List["Role"] = Relationship(
        back_populates="permissions",
        link_model=RolePermissionLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class PermissionCreate(PermissionBase):
    pass


class PermissionRead(PermissionBase):
    id: int
    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Role
# ──────────────────────────────────────────────

class RoleBase(SQLModel):
    name:        RoleName      = Field(unique=True, index=True)
    description: Optional[str] = Field(default=None, max_length=255)


class Role(RoleBase, table=True):
    __tablename__ = "roles"
    id:         Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime      = Field(default_factory=datetime.utcnow)

    permissions: List[Permission] = Relationship(
        back_populates="roles",
        link_model=RolePermissionLink,
        sa_relationship_kwargs={"lazy": "selectin"},   # ← always eager
    )
    users: List["User"] = Relationship(
        back_populates="roles",
        link_model=UserRoleLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )


class RoleCreate(RoleBase):
    permission_ids: List[int] = []


class RoleRead(RoleBase):
    id:          int
    created_at:  datetime
    permissions: List[PermissionRead] = []
    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# User
# ──────────────────────────────────────────────

class UserBase(SQLModel):
    full_name: str  = Field(max_length=150)
    email:     str  = Field(unique=True, index=True, max_length=255)
    is_active: bool = Field(default=True)


class User(UserBase, table=True):
    __tablename__ = "users"

    id:              Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str           = Field(max_length=255)
    created_at:      datetime      = Field(default_factory=datetime.utcnow)
    updated_at:      datetime      = Field(default_factory=datetime.utcnow)

    roles: List[Role] = Relationship(
        back_populates="users",
        link_model=UserRoleLink,
        sa_relationship_kwargs={"lazy": "selectin"},   # ← always eager
    )
    categories: List["Category"] = Relationship(
        back_populates="users",
        link_model=UserCategoryLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )

    def has_permission(self, action: PermissionAction) -> bool:
        for role in self.roles:
            for perm in role.permissions:
                if perm.action == action:
                    return True
        return False

    def is_admin(self) -> bool:
        return any(r.name == RoleName.ADMIN for r in self.roles)


# ── Helper: load user with all relationships eagerly ──────────────
def get_user_with_roles(session: Session, user_id: int) -> Optional["User"]:
    """
    Fetch a User with roles + permissions fully loaded using selectinload.
    Use this anywhere you need to serialise the user after the session closes.
    """
    result = session.exec(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles).selectinload(Role.permissions),  # type: ignore[arg-type]
            selectinload(User.categories),  # type: ignore[arg-type]
        )
    ).first()
    return result


# ── Pydantic schemas ──────────────────────────

class UserCreate(UserBase):
    password: str
    role_ids: List[int] = []
    category_ids: List[int] = []


class UserUpdate(SQLModel):
    full_name: Optional[str]       = None
    email:     Optional[str]       = None
    is_active: Optional[bool]      = None
    role_ids:  Optional[List[int]] = None
    category_ids: Optional[List[int]] = None


class AssignedCategoryRead(SQLModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    model_config = {"from_attributes": True}


class UserRead(UserBase):
    id:         int
    created_at: datetime
    updated_at: datetime
    roles:      List[RoleRead] = []
    categories: List[AssignedCategoryRead] = []
    model_config = {"from_attributes": True}


class UserReadShort(SQLModel):
    id:        int
    full_name: str
    email:     str
    model_config = {"from_attributes": True}
