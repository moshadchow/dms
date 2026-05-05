"""
users/schemas.py
────────────────
All Pydantic request / response schemas for the Users, Roles,
and Permissions endpoints.

Separation of concerns
───────────────────────
- SQLModel table classes  (models.py)  → database layer
- Pydantic schemas        (schemas.py) → API boundary (validation + serialisation)

This keeps the API contract decoupled from the ORM so that adding a
database column never accidentally exposes it to clients.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from users.models import PermissionAction, RoleName


# ══════════════════════════════════════════════
# Permission Schemas
# ══════════════════════════════════════════════

class PermissionResponse(BaseModel):
    """Read-only permission representation returned to clients."""

    id:          int
    action:      PermissionAction
    description: Optional[str] = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# Role Schemas
# ══════════════════════════════════════════════

class RoleCreateRequest(BaseModel):
    """Body for POST /users/roles — Admin only."""

    name:           RoleName
    description:    Optional[str]  = Field(None, max_length=255)
    permission_ids: List[int]      = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    """Body for PATCH /users/roles/{role_id} — Admin only."""

    description:    Optional[str]  = Field(None, max_length=255)
    permission_ids: Optional[List[int]] = None


class RoleResponse(BaseModel):
    """Full role detail with its assigned permissions."""

    id:          int
    name:        RoleName
    description: Optional[str]
    created_at:  datetime
    permissions: List[PermissionResponse] = []

    model_config = {"from_attributes": True}


class RoleShortResponse(BaseModel):
    """Lightweight role projection embedded inside UserResponse."""

    id:   int
    name: RoleName

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# User — Create
# ══════════════════════════════════════════════

class UserCreateRequest(BaseModel):
    """
    Body for POST /users — Admin only.

    Password rules (enforced by validator):
      • Minimum 8 characters
      • At least one uppercase letter
      • At least one digit
    """

    full_name: str       = Field(..., min_length=2, max_length=150,
                                 examples=["Jane Doe"])
    email:     EmailStr  = Field(..., examples=["jane@company.com"])
    password:  str       = Field(..., min_length=8, max_length=128)
    is_active: bool      = Field(True)
    role_ids:  List[int] = Field(default_factory=list,
                                 description="IDs of roles to assign to this user")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ══════════════════════════════════════════════
# User — Update
# ══════════════════════════════════════════════

class UserUpdateRequest(BaseModel):
    """
    Body for PATCH /users/{user_id} — Admin only.
    All fields are optional; only provided fields are applied.
    """

    full_name: Optional[str]       = Field(None, min_length=2, max_length=150)
    email:     Optional[EmailStr]  = None
    is_active: Optional[bool]      = None
    role_ids:  Optional[List[int]] = Field(
        None,
        description="Replaces the user's entire role assignment",
    )


# ══════════════════════════════════════════════
# User — Responses
# ══════════════════════════════════════════════

class UserResponse(BaseModel):
    """Full user profile returned on create / get / update."""

    id:         int
    full_name:  str
    email:      str
    is_active:  bool
    created_at: datetime
    updated_at: datetime
    roles:      List[RoleShortResponse] = []

    model_config = {"from_attributes": True}


class UserDetailResponse(UserResponse):
    """Extended profile — includes full role + permission detail.
    Used by GET /users/{user_id} and GET /auth/me."""

    roles: List[RoleResponse] = []


class UserShortResponse(BaseModel):
    """Minimal projection embedded inside document / directory responses."""

    id:        int
    full_name: str
    email:     str

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# User — List
# ══════════════════════════════════════════════

class UserListResponse(BaseModel):
    """Paginated user list returned by GET /users."""

    total: int
    skip:  int
    limit: int
    items: List[UserResponse]


# ══════════════════════════════════════════════
# User — Admin Actions
# ══════════════════════════════════════════════

class DeactivateResponse(BaseModel):
    """Returned after POST /users/{user_id}/deactivate."""

    detail:    str
    user_id:   int
    is_active: bool


class AssignRolesRequest(BaseModel):
    """Body for POST /users/{user_id}/roles — assign roles without full update."""

    role_ids: List[int] = Field(..., min_length=1)


# ══════════════════════════════════════════════
# Permission Matrix (used in Admin Panel)
# ══════════════════════════════════════════════

class RolePermissionMatrixRow(BaseModel):
    """One row in the RBAC permission matrix shown in the admin UI."""

    role:     RoleName
    view:     bool = False
    download: bool = False
    create:   bool = False
    update:   bool = False
    delete:   bool = False

    model_config = {"from_attributes": True}


class PermissionMatrixResponse(BaseModel):
    """Full matrix for all roles — GET /users/permissions/matrix."""

    matrix: List[RolePermissionMatrixRow]
