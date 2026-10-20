from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class ScanStatus(str, Enum):
    PENDING = "pending"
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"
    TIMEOUT = "timeout"


class AntivirusScan(SQLModel, table=True):
    __tablename__ = "antivirus_scans"

    id: Optional[int] = Field(default=None, primary_key=True)
    storage_path: str = Field(max_length=512, index=True)
    file_hash: str = Field(max_length=64, index=True)  # SHA-256 hex
    scan_engine: str = Field(max_length=100)
    scan_status: ScanStatus = Field(default=ScanStatus.PENDING, index=True)
    threat_name: Optional[str] = Field(default=None, max_length=255)
    scan_duration_ms: Optional[int] = Field(default=None, ge=0)
    scanned_at: Optional[datetime] = Field(default=None, index=True)
    company_id: int = Field(foreign_key="companies.id", index=True)

    company: "Company" = Relationship(  # type: ignore[assignment]
        
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# Update Document model to add av_scan_id FK
# This will be done in documents/models.py