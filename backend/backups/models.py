"""
Backup Models (spec 35)
───────────────────────
Company-wise folder backup run history. Each row records one attempt to
archive a company's storage namespace into a zip under BACKUP_ROOT.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel


class BackupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class BackupTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class BackupRun(SQLModel, table=True):
    __tablename__ = "backup_runs"
    __table_args__ = (
        Index("ix_backup_runs_company_created", "company_id", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="companies.id", index=True)
    status: BackupStatus = Field(default=BackupStatus.PENDING, index=True)
    trigger: BackupTrigger = Field(default=BackupTrigger.MANUAL)
    triggered_by: Optional[int] = Field(default=None, foreign_key="users.id")
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    file_count: int = 0                       # files archived
    total_bytes: int = 0                      # uncompressed bytes
    # POSIX path relative to BACKUP_ROOT (e.g. "acme/backup_20261021T093000Z.zip").
    # NULL means the archive was pruned by the retention policy.
    archive_path: Optional[str] = Field(default=None, max_length=500)
    archive_size_bytes: Optional[int] = None  # zip size on disk
    error_message: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    # Two FKs on this table — relationships must be disambiguated explicitly.
    company: "Company" = Relationship(  # type: ignore[assignment]
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "BackupRun.company_id"},
    )
    trigger_user: Optional["User"] = Relationship(  # type: ignore[assignment]
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "BackupRun.triggered_by"},
    )


# ──────────────────────────────────────────────
# Read schemas
# ──────────────────────────────────────────────

class BackupRunRead(SQLModel):
    id: int
    company_id: int
    company_short_name: Optional[str] = None
    status: BackupStatus
    trigger: BackupTrigger
    triggered_by: Optional[int] = None
    triggered_by_name: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    file_count: int
    total_bytes: int
    archive_path: Optional[str] = None
    archive_size_bytes: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BackupRunListResponse(SQLModel):
    total: int
    page: int
    limit: int
    items: list[BackupRunRead]
    next_page: Optional[int] = None
    prev_page: Optional[int] = None

    @classmethod
    def build(
        cls,
        items: list[BackupRunRead],
        total: int,
        skip: int,
        limit: int,
    ) -> "BackupRunListResponse":
        page = skip // limit + 1
        return cls(
            total=total,
            page=page,
            limit=limit,
            items=items,
            next_page=page + 1 if skip + limit < total else None,
            prev_page=page - 1 if page > 1 else None,
        )


class BackupSettingsRead(SQLModel):
    """Current backup schedule policy (backed by `system_settings` keys)."""
    enabled: bool
    interval_hours: int
    retention_count: int
