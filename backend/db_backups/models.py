"""
Database Backup Models (spec 36)
─────────────────────────────────
Whole-database (PostgreSQL) dump run history. Each row records one attempt
to run `pg_dump` against `dms_db` into a file under DB_BACKUP_ROOT.

Deployment-scoped: there is deliberately **no company_id**. A dump contains
every company's rows in one file, so it cannot belong to one tenant — and
it is why every route in db_backups/router.py is SuperAdmin-only.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class DbBackupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class DbBackupTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class DbBackupRun(SQLModel, table=True):
    __tablename__ = "db_backup_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: DbBackupStatus = Field(default=DbBackupStatus.PENDING, index=True)
    trigger: DbBackupTrigger = Field(default=DbBackupTrigger.MANUAL)
    triggered_by: Optional[int] = Field(default=None, foreign_key="users.id")
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    # POSIX path relative to DB_BACKUP_ROOT (e.g. "dms_20261022T093000Z.dump").
    # NULL means the dump file was pruned by the retention policy — the row
    # and its audit trail survive, the bytes do not.
    dump_path: Optional[str] = Field(default=None, max_length=500)
    dump_size_bytes: Optional[int] = None
    duration_ms: Optional[int] = None
    # `pg_dump --version` output — which client produced the archive, which
    # matters when restoring into a different major version later.
    pg_dump_version: Optional[str] = Field(default=None, max_length=60)
    error_message: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


# ──────────────────────────────────────────────
# Read schemas
# ──────────────────────────────────────────────

class DbBackupRunRead(SQLModel):
    id: int
    status: DbBackupStatus
    trigger: DbBackupTrigger
    triggered_by: Optional[int] = None
    triggered_by_name: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    dump_path: Optional[str] = None
    dump_size_bytes: Optional[int] = None
    duration_ms: Optional[int] = None
    pg_dump_version: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DbBackupRunListResponse(SQLModel):
    total: int
    page: int
    limit: int
    items: list[DbBackupRunRead]
    next_page: Optional[int] = None
    prev_page: Optional[int] = None

    @classmethod
    def build(
        cls,
        items: list[DbBackupRunRead],
        total: int,
        skip: int,
        limit: int,
    ) -> "DbBackupRunListResponse":
        page = skip // limit + 1
        return cls(
            total=total,
            page=page,
            limit=limit,
            items=items,
            next_page=page + 1 if skip + limit < total else None,
            prev_page=page - 1 if page > 1 else None,
        )


class DbBackupSettingsRead(SQLModel):
    """Current dump schedule policy (backed by `system_settings` keys)."""
    enabled: bool
    interval_hours: int
    retention_count: int
