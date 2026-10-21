"""
Backup Schemas (spec 35)
────────────────────────
Request schemas. Read schemas live in backups/models.py (module convention).
"""

from pydantic import BaseModel, Field


class BackupSettingsUpdate(BaseModel):
    """Request body for updating the backup schedule settings."""

    enabled: bool
    interval_hours: int = Field(ge=1, le=168, description="Hours between scheduled runs (1-168)")
    retention_count: int = Field(ge=1, le=100, description="Archives kept per company (1-100)")
