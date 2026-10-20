from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from antivirus.models import ScanStatus


class AntivirusScanRead(BaseModel):
    id: int
    storage_path: str
    file_hash: str
    scan_engine: str
    scan_status: ScanStatus
    threat_name: Optional[str] = None
    scan_duration_ms: Optional[int] = None
    scanned_at: Optional[datetime] = None
    company_id: int

    model_config = {"from_attributes": True}


class AntivirusScanListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[AntivirusScanRead]
    next_page: Optional[int] = None
    prev_page: Optional[int] = None

    @classmethod
    def build(
        cls,
        items: list[AntivirusScanRead],
        total: int,
        skip: int,
        limit: int,
    ) -> "AntivirusScanListResponse":
        page = skip // limit + 1
        return cls(
            total=total,
            page=page,
            limit=limit,
            items=items,
            next_page=page + 1 if skip + limit < total else None,
            prev_page=page - 1 if page > 1 else None,
        )


class RescanRequest(BaseModel):
    """Request body for manual rescan (currently empty, for future options)."""
    pass


class RescanResponse(BaseModel):
    scan_id: int
    new_status: ScanStatus
    message: str