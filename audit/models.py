from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class AuditAction(str, Enum):
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    FAILED_LOGIN = "failed_login"
    PASSWORD_CHANGED = "password_changed"
    TOKEN_REFRESH = "token_refresh"

    # User Management
    CREATE_USER = "create_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    DEACTIVATE_USER = "deactivate_user"
    ACTIVATE_USER = "activate_user"
    ASSIGN_ROLE = "assign_role"
    REMOVE_ROLE = "remove_role"
    ASSIGN_USER_LEVEL = "assign_user_level"
    REMOVE_USER_LEVEL = "remove_user_level"

    # Document Management
    UPLOAD_DOCUMENT = "upload_document"
    UPDATE_DOCUMENT = "update_document"
    DELETE_DOCUMENT = "delete_document"
    DOWNLOAD_DOCUMENT = "download_document"
    PREVIEW_DOCUMENT = "preview_document"
    VIEW_DOCUMENT = "view_document"
    MOVE_DOCUMENT = "move_document"
    RENAME_DOCUMENT = "rename_document"
    ARCHIVE_DOCUMENT = "archive_document"
    RESTORE_DOCUMENT = "restore_document"

    # Folder Management
    CREATE_DIRECTORY = "create_directory"
    RENAME_DIRECTORY = "rename_directory"
    DELETE_DIRECTORY = "delete_directory"
    MOVE_DIRECTORY = "move_directory"

    # Administration
    CREATE_CATEGORY = "create_category"
    UPDATE_CATEGORY = "update_category"
    DELETE_CATEGORY = "delete_category"
    CREATE_USER_LEVEL = "create_user_level"
    UPDATE_USER_LEVEL = "update_user_level"
    DELETE_USER_LEVEL = "delete_user_level"
    CREATE_ROLE = "create_role"

    # Security
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PERMISSION_DENIED = "permission_denied"


class AuditModule(str, Enum):
    AUTH = "auth"
    USERS = "users"
    DOCUMENTS = "documents"
    DIRECTORIES = "directories"
    CATEGORIES = "categories"
    USER_LEVELS = "user_levels"
    SECURITY = "security"


# ──────────────────────────────────────────────
# Database Table
# ──────────────────────────────────────────────

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    username: Optional[str] = Field(default=None, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=150)
    auth_provider: Optional[str] = Field(default=None, max_length=20)
    role: Optional[str] = Field(default=None, max_length=50)
    user_level: Optional[str] = Field(default=None, max_length=50)
    module: str = Field(max_length=50, index=True)
    entity_name: Optional[str] = Field(default=None, max_length=100, index=True)
    entity_id: Optional[str] = Field(default=None, max_length=50)
    action: str = Field(max_length=50, index=True)
    old_value: Optional[str] = Field(default=None)
    new_value: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None, max_length=500)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    browser: Optional[str] = Field(default=None, max_length=100)
    operating_system: Optional[str] = Field(default=None, max_length=100)
    device: Optional[str] = Field(default=None, max_length=100)
    request_url: Optional[str] = Field(default=None, max_length=500)
    http_method: Optional[str] = Field(default=None, max_length=10)
    http_status: Optional[int] = Field(default=None)
    session_id: Optional[str] = Field(default=None, max_length=100)
    correlation_id: Optional[str] = Field(default=None, max_length=100)
    is_success: bool = Field(default=True, index=True)
    failure_reason: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Pydantic Schemas
# ──────────────────────────────────────────────

class AuditLogRead(SQLModel):
    id: int
    timestamp: datetime
    user_id: Optional[int] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    auth_provider: Optional[str] = None
    role: Optional[str] = None
    user_level: Optional[str] = None
    module: str
    entity_name: Optional[str] = None
    entity_id: Optional[str] = None
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    description: Optional[str] = None
    ip_address: Optional[str] = None
    browser: Optional[str] = None
    operating_system: Optional[str] = None
    device: Optional[str] = None
    request_url: Optional[str] = None
    http_method: Optional[str] = None
    http_status: Optional[int] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    is_success: bool
    failure_reason: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class AuditLogListResponse(SQLModel):
    total: int
    page: int
    limit: int
    items: list[AuditLogRead]
