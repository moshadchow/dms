from typing import List

from pydantic import BaseModel


def _human_size(size_bytes: int) -> str:
    """Convert bytes to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.2f} GB"


class CategoryStorageUsage(BaseModel):
    category_id: int
    category_name: str
    db_size: int
    db_size_human: str
    disk_size: int
    disk_size_human: str
    document_count: int
    usage_percentage: float


class StorageUsageResponse(BaseModel):
    total_capacity: int
    total_capacity_human: str
    db_used: int
    db_used_human: str
    disk_used: int
    disk_used_human: str
    available_storage: int
    available_storage_human: str
    usage_percentage: float
    categories: List[CategoryStorageUsage]


class CapacityUpdateRequest(BaseModel):
    capacity_gb: float


class CapacityResponse(BaseModel):
    capacity_gb: float
