"""
Backup Router (spec 35)
───────────────────────
Thin router — business logic belongs in BackupService (backups/service.py).
All routes are admin-level: the `AdminUser` parameter annotation is the
authoritative per-endpoint guard (ADMIN + SUPERADMIN; company scoping and
the SUPERADMIN mutation denial happen in the service), while the coarse
permission checks come from the ROUTE_PERMISSION_MAP entries in
middleware/rbac.py.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session

from backups.models import BackupRunListResponse, BackupRunRead, BackupSettingsRead
from backups.schemas import BackupSettingsUpdate
from backups.service import BackupService, is_superadmin
from core.database import get_session
from core.dependencies import AdminUser

router = APIRouter()


@router.get(
    "",
    response_model=BackupRunListResponse,
    summary="List backup runs (Admin only)",
)
def list_backup_runs(
    company_id: Optional[int] = Query(None, description="Filter by company (Super Admin only)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    """
    Backup run history. ADMIN is auto-scoped to its own company
    (a client-supplied company_id is ignored); SUPERADMIN sees all
    companies, optionally filtered by company_id.
    """
    svc = BackupService(session)
    runs, total = svc.list_for_user(current_user, company_id, skip, limit)
    return BackupRunListResponse.build(
        items=[svc.to_read(r) for r in runs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/run",
    response_model=BackupRunRead,
    summary="Trigger an immediate backup of the caller's company (Admin only)",
)
def trigger_backup(
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    """
    Back up the caller's company folder now and return the finished run —
    `status` may be `failed` (failure is data, not an error response).
    Returns 409 if a run for the company is already in progress.
    """
    svc = BackupService(session)
    run = svc.run_manual_backup(current_user)
    return svc.to_read(run)


@router.get(
    "/settings",
    response_model=BackupSettingsRead,
    summary="Read backup schedule settings (Admin only)",
)
def read_backup_settings(
    _admin: AdminUser = None,
    session: Session = Depends(get_session),
):
    return BackupService(session).get_settings()


@router.put(
    "/settings",
    response_model=BackupSettingsRead,
    summary="Update backup schedule settings (Admin only)",
)
def update_backup_settings(
    payload: BackupSettingsUpdate,
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    return BackupService(session).update_settings(payload, actor=current_user)


@router.get(
    "/{run_id}",
    response_model=BackupRunRead,
    summary="Backup run detail (Admin only)",
)
def get_backup_run(
    run_id: int,
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    """One run's detail; another company's run id resolves to 404."""
    scope = None if is_superadmin(current_user) else current_user.company_id
    svc = BackupService(session)
    run = svc.get_run(run_id, scope)
    if not run:
        raise HTTPException(status_code=404, detail="Backup run not found")
    return svc.to_read(run)


@router.get(
    "/{run_id}/download",
    summary="Download a backup archive (Admin only)",
)
def download_backup(
    run_id: int,
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    """Stream the zip archive; pruned archives return 404 with a reason."""
    scope = None if is_superadmin(current_user) else current_user.company_id
    svc = BackupService(session)
    run = svc.get_run(run_id, scope)
    if not run:
        raise HTTPException(status_code=404, detail="Backup run not found")
    path = svc.download_path(run)
    svc.log_download(run, current_user)
    filename = Path(run.archive_path.replace("\\", "/")).name
    return FileResponse(path, media_type="application/zip", filename=filename)
