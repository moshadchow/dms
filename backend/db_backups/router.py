"""
Database Backup Router (spec 36)
─────────────────────────────────
Thin router — business logic belongs in DbBackupService (db_backups/service.py).

Every route is **SUPERADMIN-only**, enforced by the `SuperAdminUser`
parameter annotation (the authoritative per-endpoint guard). A pg_dump of
dms_db contains every company's rows in one file, so a *company* ADMIN
must never reach it — that would be a cross-tenant leak. The
ROUTE_PERMISSION_MAP entries in middleware/rbac.py are only the coarse
pre-filter, and ADMIN bypasses them entirely via User.is_admin().

ROUTE REGISTRATION ORDER MATTERS: FastAPI matches in registration order,
not URL specificity. `/settings` must be declared BEFORE `/{run_id}`,
otherwise "settings" would be captured as a run_id and answer 422.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session

from core.database import get_session
from core.dependencies import SuperAdminUser
from db_backups.models import DbBackupRunListResponse, DbBackupRunRead, DbBackupSettingsRead
from db_backups.schemas import DbBackupSettingsUpdate
from db_backups.service import DbBackupService

router = APIRouter()


@router.get(
    "",
    response_model=DbBackupRunListResponse,
    summary="List database backup runs (Super Admin only)",
)
def list_db_backup_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _superadmin: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    """
    Dump run history, newest first. No company filter: a database dump is
    deployment-scoped and spans every company.
    """
    svc = DbBackupService(session)
    runs, total = svc.list_runs(skip, limit)
    return DbBackupRunListResponse.build(
        items=svc.to_reads(runs),
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/run",
    response_model=DbBackupRunRead,
    summary="Dump the database now (Super Admin only)",
)
def run_db_backup(
    _superadmin: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    """
    Dump `dms_db` now and return the finished run — `status` may be
    `failed` (failure is data, not an error response).
    Returns 409 if a dump is already in progress.
    """
    svc = DbBackupService(session)
    run = svc.run_manual_dump(_superadmin)
    return svc.to_read(run)


@router.get(
    "/settings",
    response_model=DbBackupSettingsRead,
    summary="Read database backup settings (Super Admin only)",
)
def read_db_backup_settings(
    _superadmin: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    return DbBackupService(session).get_settings()


@router.put(
    "/settings",
    response_model=DbBackupSettingsRead,
    summary="Update database backup settings (Super Admin only)",
)
def update_db_backup_settings(
    payload: DbBackupSettingsUpdate,
    current_user: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    return DbBackupService(session).update_settings(payload, actor=current_user)


@router.get(
    "/{run_id}",
    response_model=DbBackupRunRead,
    summary="Database backup run detail (Super Admin only)",
)
def get_db_backup_run(
    run_id: int,
    _superadmin: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    """One run's detail; an unknown id resolves to 404."""
    svc = DbBackupService(session)
    run = svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Database backup run not found")
    return svc.to_read(run)


@router.get(
    "/{run_id}/download",
    summary="Download a database dump (Super Admin only)",
)
def download_db_backup(
    run_id: int,
    current_user: SuperAdminUser = None,
    session: Session = Depends(get_session),
):
    """Stream the dump file; a pruned dump returns 404 with a reason."""
    svc = DbBackupService(session)
    run = svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Database backup run not found")
    path = svc.download_path(run)
    svc.log_download(run, current_user)
    filename = Path(run.dump_path.replace("\\", "/")).name  # type: ignore[union-attr]
    # pg_dump custom format is gzip-compressed but not a registered type.
    return FileResponse(path, media_type="application/octet-stream", filename=filename)
