"""RBAC models — re-exported from users.models for backward compatibility.

The canonical definitions live in users/models.py because User and Role
have bidirectional relationships through UserRoleLink. This module exists
so new code can import RBAC-specific types from a focused namespace.
"""
from users.models import (  # noqa: F401
    AuthProvider,
    Permission,
    PermissionAction,
    PermissionBase,
    PermissionCreate,
    PermissionRead,
    Role,
    RoleBase,
    RoleCreate,
    RoleName,
    RolePermissionLink,
    RoleRead,
    UserRoleLink,
)
