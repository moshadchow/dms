"""
Backup Service (spec 35)
────────────────────────
Company-wise folder backup: each company's storage namespace
(STORAGE_ROOT/<short_name>/) is archived into a timestamped zip under
BACKUP_ROOT/<short_name>/ — on a schedule (backups/scheduler.py) or on
demand (admin trigger). Run history lives in `backup_runs`; the schedule
policy lives in the `system_settings` key/value store (same pattern as
`storage_capacity_gb`).

BACKUP_ROOT must stay OUTSIDE STORAGE_ROOT: a backup must never contain
itself, and storage-usage/quota accounting must not double-count archives.
"""

import logging
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from backups.models import (
    BackupRun,
    BackupRunRead,
    BackupSettingsRead,
    BackupStatus,
    BackupTrigger,
)
from backups.schemas import BackupSettingsUpdate
from company_profile.models import Company
from core.config import APP_ROOT, get_settings
from core.storage import storage_service
from storage_usage.models import SystemSetting
from users.models import RoleName, User

logger = logging.getLogger("dms.backups")

# ── SystemSetting keys (seeded idempotently in seed.py) ──────────
BACKUP_ENABLED_KEY    = "backup_enabled"
BACKUP_INTERVAL_KEY   = "backup_interval_hours"
BACKUP_RETENTION_KEY  = "backup_retention_count"

DEFAULT_INTERVAL_HOURS  = 24
DEFAULT_RETENTION_COUNT = 7


def is_superadmin(user: User) -> bool:
    """SUPERADMIN check — mirrors core/dependencies.py::require_superadmin."""
    return any(r.name == RoleName.SUPERADMIN for r in user.roles)


# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────

def get_backup_root() -> Path:
    """
    Absolute backup root. A relative BACKUP_ROOT is resolved against the
    application root (the directory holding `core/`), never against the
    process working directory — the same resolution STORAGE_ROOT gets, so
    the tree is identical no matter where uvicorn was launched from. An
    absolute value is used as-is.
    """
    raw = Path(get_settings().BACKUP_ROOT).expanduser()
    if not raw.is_absolute():
        raw = APP_ROOT / raw
    return raw.resolve()


def _company_backup_dir(company: Company) -> Path:
    """
    BACKUP_ROOT/<short_name>/ — the short_name is validated through the same
    storage guard used for the live tree (filesystem safety + path-traversal
    checks), and BACKUP_ROOT must stay outside STORAGE_ROOT.
    """
    safe_name = storage_service._validate_short_name(company.short_name)
    backup_root  = get_backup_root()
    storage_root = storage_service.storage_root
    try:
        backup_root.relative_to(storage_root)
    except ValueError:
        pass
    else:
        raise RuntimeError(
            "BACKUP_ROOT must be outside STORAGE_ROOT "
            f"(BACKUP_ROOT={backup_root}, STORAGE_ROOT={storage_root})"
        )
    return backup_root / safe_name


def _create_zip(company_root: Path, zip_path: Path) -> Tuple[int, int]:
    """
    Zip company_root into zip_path. Arcnames are relative to the company
    root so unzipping restores the exact folder tree (uploads/, memos/, ...).
    ZipFile.write streams each member through the compressor in small
    chunks — files are never held in memory whole.

    Returns (file_count, total_uncompressed_bytes).
    """
    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src in sorted(company_root.rglob("*")):
            if not src.is_file():
                continue
            zf.write(src, src.relative_to(company_root).as_posix())
            file_count += 1
            total_bytes += src.stat().st_size
    return file_count, total_bytes


# ──────────────────────────────────────────────
# SystemSetting helpers
# ──────────────────────────────────────────────

def _get_setting(session: Session, key: str, default: str) -> str:
    row = session.get(SystemSetting, key)
    return row.value if row else default


def _get_int_setting(session: Session, key: str, default: int) -> int:
    raw = _get_setting(session, key, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid value for system setting %s: %r — using default %d", key, raw, default)
        return default


def _set_setting(session: Session, key: str, value: str, description: str) -> None:
    row = session.get(SystemSetting, key)
    if row:
        row.value = value
    else:
        session.add(SystemSetting(key=key, value=value, description=description))


# ──────────────────────────────────────────────
# Backup Service
# ──────────────────────────────────────────────

class BackupService:
    """Class-based backup service — takes a Session (module convention)."""

    def __init__(self, session: Session):
        self.session = session

    # ── Schedule settings ────────────────────────

    def get_settings(self) -> BackupSettingsRead:
        return BackupSettingsRead(
            enabled=_get_setting(self.session, BACKUP_ENABLED_KEY, "true").strip().lower() == "true",
            interval_hours=max(1, _get_int_setting(self.session, BACKUP_INTERVAL_KEY, DEFAULT_INTERVAL_HOURS)),
            retention_count=max(1, _get_int_setting(self.session, BACKUP_RETENTION_KEY, DEFAULT_RETENTION_COUNT)),
        )

    def update_settings(self, payload: BackupSettingsUpdate, actor: Optional[User] = None) -> BackupSettingsRead:
        """Persist the schedule policy and audit the change."""
        _set_setting(self.session, BACKUP_ENABLED_KEY,
                     "true" if payload.enabled else "false",
                     "Company-wise folder backup scheduler enabled")
        _set_setting(self.session, BACKUP_INTERVAL_KEY,
                     str(payload.interval_hours),
                     "Hours between scheduled company backups")
        _set_setting(self.session, BACKUP_RETENTION_KEY,
                     str(payload.retention_count),
                     "Archives kept per company before pruning")
        self.session.commit()

        AuditService(self.session).log_event(
            action=AuditAction.UPDATE_BACKUP_SETTINGS,
            module=AuditModule.BACKUPS,
            company_id=actor.company_id if actor else None,
            user=actor,
            entity_name="BackupSettings",
            new_value=payload.model_dump(),
            description="Backup schedule settings updated",
        )
        return self.get_settings()

    # ── Run history ──────────────────────────────

    def list_runs(
        self,
        company_id: Optional[int],
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[list[BackupRun], int]:
        conditions = []
        if company_id is not None:
            conditions.append(BackupRun.company_id == company_id)

        total = self.session.exec(
            select(func.count(BackupRun.id)).where(*conditions)
        ).one()

        rows = self.session.exec(
            select(BackupRun)
            .where(*conditions)
            .order_by(BackupRun.created_at.desc(), BackupRun.id.desc())
            .offset(skip)
            .limit(limit)
        ).all()
        return list(rows), int(total)

    def list_for_user(
        self,
        user: User,
        company_id_filter: Optional[int],
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[list[BackupRun], int]:
        """
        Company scoping for reads: ADMIN is auto-scoped to its own company
        (a client-supplied company_id is ignored, not honored); SUPERADMIN
        sees all companies, optionally filtered by company_id.
        """
        if is_superadmin(user):
            return self.list_runs(company_id_filter, skip, limit)
        if user.company_id is None:
            return [], 0  # company-less admin sees an empty list
        return self.list_runs(user.company_id, skip, limit)

    def get_run(self, run_id: int, company_id: Optional[int]) -> Optional[BackupRun]:
        """
        Fetch one run, company-scoped. `company_id=None` (SUPERADMIN) sees
        all; otherwise a cross-company id resolves to None → 404 upstream
        (non-admin denials are 404 by design — oracle avoidance).
        """
        run = self.session.get(BackupRun, run_id)
        if not run:
            return None
        if company_id is not None and run.company_id != company_id:
            return None
        return run

    # ── Execution ────────────────────────────────

    def run_manual_backup(self, user: User) -> BackupRun:
        """
        Resolve the caller's company and run a manual backup (ADMIN owns
        its company only). SUPERADMIN is denied here — the service layer,
        per the repo invariant that SUPERADMIN mutations on company-scoped
        resources are 403.
        """
        if is_superadmin(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin cannot trigger company backups",
            )
        if not user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No company assigned",
            )
        company = self.session.get(Company, user.company_id)
        if not company or not company.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Company is inactive or missing",
            )
        return self.run_backup(company, user=user, trigger=BackupTrigger.MANUAL)

    def run_backup(
        self,
        company: Company,
        user: Optional[User] = None,
        trigger: BackupTrigger = BackupTrigger.MANUAL,
    ) -> BackupRun:
        """
        Run one backup for `company`. The outcome — success or failure — is
        recorded on the run row: failure is data, not an error response.
        """
        already_running = self.session.exec(
            select(BackupRun).where(
                BackupRun.company_id == company.id,
                BackupRun.status == BackupStatus.RUNNING,
            )
        ).first()
        if already_running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A backup for this company is already running",
            )

        run = BackupRun(
            company_id=company.id,
            status=BackupStatus.RUNNING,
            trigger=trigger,
            triggered_by=user.id if user else None,
            started_at=datetime.utcnow(),
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        try:
            self._execute(run, company)
        except Exception as exc:
            run.status = BackupStatus.FAILED
            run.finished_at = datetime.utcnow()
            run.error_message = str(exc)[:500]
            self.session.add(run)
            self.session.commit()
            AuditService(self.session).log_event(
                action=AuditAction.BACKUP_FAILED,
                module=AuditModule.BACKUPS,
                company_id=company.id,
                user=user,
                entity_name="BackupRun",
                entity_id=str(run.id),
                description=f"Backup failed: {run.error_message}",
                is_success=False,
                failure_reason=run.error_message,
            )
            logger.error("Backup failed for company %s: %s", company.short_name, run.error_message)
            return run

        AuditService(self.session).log_event(
            action=AuditAction.CREATE_BACKUP,
            module=AuditModule.BACKUPS,
            company_id=company.id,
            user=user,
            entity_name="BackupRun",
            entity_id=str(run.id),
            new_value={
                "archive_path": run.archive_path,
                "file_count": run.file_count,
                "total_bytes": run.total_bytes,
                "trigger": trigger.value,
            },
            description=f"Company folder backup completed ({trigger.value})",
        )
        self._prune_retention(company)
        return run

    def to_read(self, run: BackupRun) -> BackupRunRead:
        company = run.company                      # selectin-loaded
        trigger_user = run.trigger_user            # selectin-loaded
        return BackupRunRead(
            id=run.id,
            company_id=run.company_id,
            company_short_name=company.short_name if company else None,
            status=run.status,
            trigger=run.trigger,
            triggered_by=run.triggered_by,
            triggered_by_name=trigger_user.full_name if trigger_user else None,
            started_at=run.started_at,
            finished_at=run.finished_at,
            file_count=run.file_count,
            total_bytes=run.total_bytes,
            archive_path=run.archive_path,
            archive_size_bytes=run.archive_size_bytes,
            error_message=run.error_message,
            created_at=run.created_at,
        )

    # ── Download ─────────────────────────────────

    def download_path(self, run: BackupRun) -> Path:
        """
        Resolve a run's archive to an absolute path. A pruned or vanished
        archive is a 404 with an explicit reason (not a bare denial).
        """
        if not run.archive_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup archive no longer exists (retention policy)",
            )
        backup_root = get_backup_root()
        # Stored values are POSIX; rows written on Windows may hold backslashes.
        abs_path = (backup_root / Path(run.archive_path.replace("\\", "/"))).resolve()
        # Path-traversal guard — must stay under BACKUP_ROOT
        try:
            abs_path.relative_to(backup_root)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid backup path",
            )
        if not abs_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup archive no longer exists (retention policy)",
            )
        return abs_path

    def log_download(self, run: BackupRun, user: Optional[User]) -> None:
        AuditService(self.session).log_event(
            action=AuditAction.DOWNLOAD_BACKUP,
            module=AuditModule.BACKUPS,
            company_id=run.company_id,
            user=user,
            entity_name="BackupRun",
            entity_id=str(run.id),
            new_value={"archive_path": run.archive_path},
            description="Backup archive downloaded",
        )

    # ── Internals ────────────────────────────────

    def _execute(self, run: BackupRun, company: Company) -> None:
        """Zip the company folder and finalize the run row as success."""
        company_root = storage_service.get_company_root(company)
        if not company_root.is_dir():
            # A missing company root means the storage *configuration* is
            # wrong — say so loudly (same message discipline as resolve_path).
            logger.warning(
                "Backup source %s does not exist (company=%s, STORAGE_ROOT=%s) "
                "— check the storage configuration",
                company_root, company.short_name, get_settings().STORAGE_ROOT,
            )
            raise RuntimeError("Company storage folder does not exist on disk")

        backup_dir = _company_backup_dir(company)
        backup_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        zip_path = backup_dir / f"backup_{stamp}.zip"
        suffix = 2
        while zip_path.exists():  # two runs in the same second
            zip_path = backup_dir / f"backup_{stamp}_{suffix}.zip"
            suffix += 1

        file_count, total_bytes = _create_zip(company_root, zip_path)

        run.file_count = file_count
        run.total_bytes = total_bytes
        run.archive_path = zip_path.relative_to(get_backup_root()).as_posix()
        run.archive_size_bytes = zip_path.stat().st_size
        run.status = BackupStatus.SUCCESS
        run.finished_at = datetime.utcnow()
        self.session.add(run)
        self.session.commit()

    def _prune_retention(self, company: Company) -> None:
        """
        Keep the newest `retention_count` archives per company. Older FILES
        are deleted; their rows survive with archive_path = NULL so run
        history and audit remain intact.
        """
        retention = self.get_settings().retention_count
        stale_runs = self.session.exec(
            select(BackupRun)
            .where(
                BackupRun.company_id == company.id,
                BackupRun.archive_path.is_not(None),  # type: ignore[union-attr]
            )
            .order_by(BackupRun.created_at.desc(), BackupRun.id.desc())
            .offset(retention)
        ).all()
        if not stale_runs:
            return

        backup_root = get_backup_root()
        for run in stale_runs:
            try:
                stale = backup_root / Path(run.archive_path.replace("\\", "/"))
                if stale.is_file():
                    stale.unlink()
            except OSError:
                logger.warning("Could not delete pruned backup archive %s", run.archive_path)
            run.archive_path = None
            self.session.add(run)
        self.session.commit()


# ──────────────────────────────────────────────
# Scheduler entry point
# ──────────────────────────────────────────────

def run_due_backups(engine) -> int:
    """
    One scheduled pass: back up every active company whose last run (any
    status) is older than the configured interval — a failed run counts as
    "recently attempted" so a persistent failure cannot retry-storm the
    worker. Opens its own session, never raises.

    Returns the number of runs started. `engine` is passed in by the caller
    (backups/scheduler.py binds core.database's engine at import time, so
    tests patch it there and pass the test engine straight through).
    """
    started = 0
    with Session(engine) as session:
        try:
            svc = BackupService(session)
            policy = svc.get_settings()
            if not policy.enabled:
                return 0

            now = datetime.utcnow()
            companies = session.exec(
                select(Company).where(Company.is_active == True)  # noqa: E712
            ).all()
            for company in companies:
                last = session.exec(
                    select(BackupRun)
                    .where(BackupRun.company_id == company.id)
                    .order_by(BackupRun.created_at.desc(), BackupRun.id.desc())
                    .limit(1)
                ).first()
                if last is not None and last.created_at >= now - timedelta(hours=policy.interval_hours):
                    continue  # not due yet
                svc.run_backup(company, user=None, trigger=BackupTrigger.SCHEDULED)
                started += 1
        except Exception:
            logger.exception("Scheduled backup pass failed")
    return started
