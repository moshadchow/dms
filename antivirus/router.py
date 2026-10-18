from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from core.database import get_session
from core.dependencies import AdminUser, CurrentUser
from antivirus.schemas import (
    AntivirusScanListResponse,
    AntivirusScanRead,
    RescanRequest,
    RescanResponse,
)
from antivirus.service import AntivirusService
from users.models import PermissionAction

router = APIRouter(prefix="/antivirus", tags=["Antivirus"])


@router.get(
    "/scans",
    response_model=AntivirusScanListResponse,
    summary="List antivirus scan history",
    dependencies=[Depends(AdminUser)],  # Admin only
)
def list_scans(
    status: Optional[str] = Query(None, description="Filter by scan status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    """List scan history for current user's company (Admin only)."""
    if not current_user.company_id:
        return AntivirusScanListResponse.build([], 0, skip, limit)
    
    svc = AntivirusService(session)
    scans, total = svc.list_scans(
        company_id=current_user.company_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return AntivirusScanListResponse.build(
        items=[AntivirusScanRead.model_validate(s) for s in scans],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/scans/{scan_id}",
    response_model=AntivirusScanRead,
    summary="Get scan detail",
    dependencies=[Depends(AdminUser)],  # Admin only
)
def get_scan(
    scan_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    """Get scan detail by ID (Admin only)."""
    if not current_user.company_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Scan not found")
    
    svc = AntivirusService(session)
    scan = svc.get_scan(scan_id, current_user.company_id)
    if not scan:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return AntivirusScanRead.model_validate(scan)


@router.post(
    "/rescan/{scan_id}",
    response_model=RescanResponse,
    summary="Manually rescan a file",
    dependencies=[Depends(AdminUser)],  # Admin only
)
async def rescan_file(
    scan_id: int,
    payload: RescanRequest,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    """Trigger a manual rescan of a previously scanned file (Admin only)."""
    if not current_user.company_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="No company assigned")
    
    svc = AntivirusService(session)
    try:
        scan = await svc.rescan(scan_id, current_user.company_id)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Rescan failed: {e}")
    
    return RescanResponse(
        scan_id=scan.id,
        new_status=scan.scan_status,
        message=f"Rescan completed with status: {scan.scan_status.value}",
    )