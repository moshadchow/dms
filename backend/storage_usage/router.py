from fastapi import APIRouter, Depends
from sqlmodel import Session

from core.database import get_session
from core.dependencies import AdminUser, CurrentUser
from storage_usage.schemas import CapacityResponse, CapacityUpdateRequest, StorageUsageResponse
from storage_usage.service import get_capacity, get_storage_usage, set_capacity

router = APIRouter()


@router.get("/usage", response_model=StorageUsageResponse, summary="Get storage usage statistics (Admin only)")
def storage_usage(
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
) -> StorageUsageResponse:
    """Return overall and per-category storage usage from both DB and disk."""
    return get_storage_usage(session, current_user.company_id)


@router.get("/capacity", response_model=CapacityResponse, summary="Get storage capacity setting (Admin only)")
def read_capacity(
    _: AdminUser = None,
    session: Session = Depends(get_session),
) -> CapacityResponse:
    """Return the current configured storage capacity."""
    return get_capacity(session)


@router.put("/capacity", response_model=CapacityResponse, summary="Update storage capacity setting (Admin only)")
def update_capacity(
    body: CapacityUpdateRequest,
    _: AdminUser = None,
    session: Session = Depends(get_session),
) -> CapacityResponse:
    """Update the storage capacity setting (admin-configurable)."""
    return set_capacity(session, body.capacity_gb)
