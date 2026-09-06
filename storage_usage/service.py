import os
from pathlib import Path
from typing import Dict, List, Tuple

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from categories.models import Category
from core.config import settings
from directories.models import Directory
from documents.models import Document, DocumentStatus
from storage_usage.models import SystemSetting
from storage_usage.schemas import (
    CapacityResponse,
    CategoryStorageUsage,
    StorageUsageResponse,
    _human_size,
)

DEFAULT_CAPACITY_GB = 100


def _get_capacity_bytes(session: Session) -> int:
    """Read the configured storage capacity in bytes from system_settings."""
    row = session.get(SystemSetting, "storage_capacity_gb")
    if row:
        try:
            return int(float(row.value) * 1024 ** 3)
        except (ValueError, TypeError):
            pass
    return DEFAULT_CAPACITY_GB * 1024 ** 3


def _get_db_usage(session: Session) -> Tuple[int, List[Dict]]:
    """Aggregate file_size from the documents table, grouped by category.

    Returns (total_bytes, [{category_id, category_name, total_size, document_count}])
    Only includes categories that still exist in the categories table.
    """
    rows = (
        session.exec(
            select(
                Directory.category_id,
                func.sum(Document.file_size).label("total_size"),
                func.count(Document.id).label("doc_count"),
            )
            .join(Directory, Document.directory_id == Directory.id)
            .where(
                Document.status != DocumentStatus.DELETED,
            )
            .group_by(Directory.category_id)
        )
        .all()
    )

    total = 0
    categories: List[Dict] = []
    for row in rows:
        size = row.total_size or 0
        count = row.doc_count or 0
        total += size
        categories.append(
            {
                "category_id": row.category_id,
                "total_size": size,
                "document_count": count,
            }
        )

    # Fetch category names — drop orphaned category_ids
    cat_ids = [c["category_id"] for c in categories]
    if cat_ids:
        cat_rows = session.exec(
            select(Category).where(col(Category.id).in_(cat_ids))
        ).all()
        cat_map = {c.id: c.name for c in cat_rows}
        valid: List[Dict] = []
        for c in categories:
            name = cat_map.get(c["category_id"])
            if name is not None:
                c["category_name"] = name
                valid.append(c)
            else:
                total -= c["total_size"]
        categories = valid

    return total, categories


def _get_disk_usage() -> Tuple[int, Dict[int, int]]:
    """Walk STORAGE_ROOT and sum file sizes.

    Returns (total_bytes, {category_id: bytes})
    """
    storage_root = str(Path(settings.STORAGE_ROOT).resolve())
    if not os.path.isdir(storage_root):
        return 0, {}

    total = 0
    by_category: Dict[int, int] = {}

    for dirpath, _dirnames, filenames in os.walk(storage_root):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            try:
                size = os.path.getsize(fpath)
            except OSError:
                continue
            total += size

            # Extract category_id from path: STORAGE_ROOT/<category_id>/...
            rel = os.path.relpath(fpath, storage_root)
            parts = rel.split(os.sep)
            try:
                cat_id = int(parts[0])
                by_category[cat_id] = by_category.get(cat_id, 0) + size
            except (ValueError, IndexError):
                pass  # files not under a category directory (e.g. signatures/)

    return total, by_category


def get_storage_usage(session: Session) -> StorageUsageResponse:
    """Compute and return full storage usage stats."""
    capacity = _get_capacity_bytes(session)
    db_total, db_categories = _get_db_usage(session)
    disk_total, disk_by_cat = _get_disk_usage()

    # Use the best available measurement for total used storage.
    # disk_total is preferred (actual filesystem), but if the disk walk
    # fails or returns 0 while the DB has documents, fall back to db_total.
    total_used = max(db_total, disk_total)
    available = max(capacity - total_used, 0)
    usage_pct = (total_used / capacity * 100) if capacity > 0 else 0.0

    # Merge DB and disk data
    all_cat_ids = set()
    cat_data: Dict[int, Dict] = {}
    for c in db_categories:
        cid = c["category_id"]
        all_cat_ids.add(cid)
        cat_data[cid] = {
            "category_id": cid,
            "category_name": c["category_name"],
            "db_size": c["total_size"],
            "disk_size": disk_by_cat.get(cid, 0),
            "document_count": c["document_count"],
        }

    # Add disk-only categories that exist in the categories table
    orphan_disk_ids = [cid for cid in disk_by_cat if cid not in all_cat_ids]
    if orphan_disk_ids:
        cat_rows = session.exec(
            select(Category).where(col(Category.id).in_(orphan_disk_ids))
        ).all()
        valid_names = {c.id: c.name for c in cat_rows}
        for cid in orphan_disk_ids:
            name = valid_names.get(cid)
            if name is not None:
                all_cat_ids.add(cid)
                cat_data[cid] = {
                    "category_id": cid,
                    "category_name": name,
                    "db_size": 0,
                    "disk_size": disk_by_cat[cid],
                    "document_count": 0,
                }

    categories: List[CategoryStorageUsage] = []
    for cid in sorted(all_cat_ids):
        d = cat_data[cid]
        cat_usage_pct = (d["db_size"] / db_total * 100) if db_total > 0 else 0.0
        categories.append(
            CategoryStorageUsage(
                category_id=d["category_id"],
                category_name=d["category_name"],
                db_size=d["db_size"],
                db_size_human=_human_size(d["db_size"]),
                disk_size=d["disk_size"],
                disk_size_human=_human_size(d["disk_size"]),
                document_count=d["document_count"],
                usage_percentage=round(cat_usage_pct, 1),
            )
        )

    # Sort by db_size descending
    categories.sort(key=lambda c: c.db_size, reverse=True)

    return StorageUsageResponse(
        total_capacity=capacity,
        total_capacity_human=_human_size(capacity),
        total_used=total_used,
        total_used_human=_human_size(total_used),
        db_used=db_total,
        db_used_human=_human_size(db_total),
        disk_used=disk_total,
        disk_used_human=_human_size(disk_total),
        available_storage=available,
        available_storage_human=_human_size(available),
        usage_percentage=round(usage_pct, 1),
        categories=categories,
    )


def get_capacity(session: Session) -> CapacityResponse:
    """Return the current storage capacity setting."""
    cap_bytes = _get_capacity_bytes(session)
    return CapacityResponse(capacity_gb=round(cap_bytes / (1024 ** 3), 1))


def set_capacity(session: Session, capacity_gb: float) -> CapacityResponse:
    """Update the storage capacity setting."""
    if capacity_gb <= 0:
        raise HTTPException(status_code=422, detail="Capacity must be greater than 0")
    if capacity_gb > 10_000:
        raise HTTPException(status_code=422, detail="Capacity cannot exceed 10,000 GB")

    row = session.get(SystemSetting, "storage_capacity_gb")
    if row:
        row.value = str(capacity_gb)
    else:
        session.add(
            SystemSetting(
                key="storage_capacity_gb",
                value=str(capacity_gb),
                description="Total storage capacity in GB",
            )
        )
    session.commit()
    return CapacityResponse(capacity_gb=capacity_gb)
