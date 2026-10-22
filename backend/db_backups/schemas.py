"""
Database Backup Schemas (spec 36)
─────────────────────────────────
Request schemas. Read schemas live in db_backups/models.py (module convention).
"""

from pydantic import BaseModel, Field


class DbBackupSettingsUpdate(BaseModel):
    """Request body for updating the database dump schedule settings."""

    enabled: bool
    interval_hours: int = Field(ge=1, le=168, description="Hours between scheduled dumps (1-168)")
    retention_count: int = Field(ge=1, le=100, description="Dump files kept before pruning (1-100)")
