"""
Database Backup Service (spec 36)
──────────────────────────────────
The PostgreSQL half of disaster recovery: dump `dms_db` with `pg_dump` into a
timestamped file under DB_BACKUP_ROOT — on a schedule (db_backups/scheduler.py)
or on demand (admin trigger). Run history lives in `db_backup_runs`; the
schedule policy lives in the `system_settings` key/value store (same pattern
as `storage_capacity_gb` and spec 35's `backup_*` keys).

Deployment-scoped, therefore **no company_id anywhere in this module**: one
database holds every company, so a dump cannot belong to a single tenant.
That is also why every route is SuperAdmin-only — see db_backups/router.py.

DB_BACKUP_ROOT must stay outside STORAGE_ROOT and outside BACKUP_ROOT:
a dump must never be written into the tree it is meant to complement, and
backup archives must never contain each other.

Security invariant: the database password travels **only** in the child
process's PGPASSWORD environment variable. It is never part of argv, never
logged, and never persisted in `error_message` (anything we persist goes
through `_redact`).
"""

import logging
import os
import subprocess
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple, Optional, Tuple

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from backups.service import get_backup_root  # shared APP_ROOT resolution
from core.config import APP_ROOT, get_settings
from core.storage import storage_service
from db_backups.models import (
    DbBackupRun,
    DbBackupRunRead,
    DbBackupSettingsRead,
    DbBackupStatus,
    DbBackupTrigger,
)
from db_backups.schemas import DbBackupSettingsUpdate
from storage_usage.models import SystemSetting
from users.models import User

logger = logging.getLogger("dms.db_backups")

# ── SystemSetting keys (seeded idempotently in seed.py) ──────────
DB_BACKUP_ENABLED_KEY   = "db_backup_enabled"
DB_BACKUP_INTERVAL_KEY  = "db_backup_interval_hours"
DB_BACKUP_RETENTION_KEY = "db_backup_retention_count"

DEFAULT_INTERVAL_HOURS  = 24
DEFAULT_RETENTION_COUNT = 7


class DbDumpError(RuntimeError):
    """A dump could not be produced. Always becomes `status=failed` data —
    never an HTTP error response."""


# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────

def get_db_backup_root() -> Path:
    """
    Absolute dump root. A relative DB_BACKUP_ROOT resolves against the
    application root (the directory holding `core/`), never the process
    working directory — the same resolution STORAGE_ROOT and BACKUP_ROOT
    get, so the tree is identical wherever uvicorn was launched from.

    The root must sit OUTSIDE both STORAGE_ROOT and BACKUP_ROOT.
    """
    raw = Path(get_settings().DB_BACKUP_ROOT).expanduser()
    if not raw.is_absolute():
        raw = APP_ROOT / raw
    root = raw.resolve()

    for label, other in (
        ("STORAGE_ROOT", storage_service.storage_root),
        ("BACKUP_ROOT", get_backup_root()),
    ):
        try:
            root.relative_to(other)
        except ValueError:
            continue
        raise RuntimeError(
            f"DB_BACKUP_ROOT must be outside {label} "
            f"(DB_BACKUP_ROOT={root}, {label}={other})"
        )
    return root


# ──────────────────────────────────────────────
# Connection parsing → argv/env (no secret in argv)
# ──────────────────────────────────────────────

class DbConn(NamedTuple):
    host: str
    port: int
    user: str
    password: Optional[str]
    dbname: str
    sslmode: Optional[str]


def _parse_database_url(url: str) -> DbConn:
    """
    Split DATABASE_URL into the pieces pg_dump takes as options.

    The SQLAlchemy driver suffix is stripped (postgresql+psycopg2:// →
    postgresql://) — pg_dump has never heard of `+psycopg2`.
    """
    if not url or "://" not in url:
        raise DbDumpError("DATABASE_URL is missing or malformed")
    parts = urllib.parse.urlsplit(url)
    scheme = parts.scheme.split("+", 1)[0]
    if scheme not in ("postgresql", "postgres"):
        raise DbDumpError(f"DATABASE_URL scheme '{parts.scheme}' is not PostgreSQL")
    if not parts.hostname:
        raise DbDumpError("DATABASE_URL has no host")
    if not parts.username:
        raise DbDumpError("DATABASE_URL has no user")
    dbname = urllib.parse.unquote(parts.path.lstrip("/"))
    if not dbname:
        raise DbDumpError("DATABASE_URL has no database name")

    params = dict(urllib.parse.parse_qsl(parts.query))
    try:
        port = parts.port or 5432
    except ValueError as exc:
        raise DbDumpError(f"DATABASE_URL has an invalid port: {exc}") from None

    return DbConn(
        host=parts.hostname,
        port=port,
        user=urllib.parse.unquote(parts.username),
        password=urllib.parse.unquote(parts.password) if parts.password else None,
        dbname=dbname,
        sslmode=params.get("sslmode"),
    )


def _build_command(conn: DbConn, target_path: Path) -> list[str]:
    """
    argv for pg_dump. Pure function so a test can assert the password is
    absent without ever spawning a process.

    `--no-password` is essential: without it pg_dump would prompt on a TTY
    and hang forever when the password is wrong.
    """
    argv = [
        get_settings().PG_DUMP_PATH,
        "--format=custom",       # compressed, restorable with pg_restore
        "--no-owner",            # restorable into a different role/server
        "--no-privileges",
        "--no-password",         # never prompt — fail instead of hanging
        "--file", str(target_path),
        "--host", conn.host,
        "--port", str(conn.port),
        "--username", conn.user,
    ]
    if conn.sslmode:
        argv += ["--sslmode", conn.sslmode]
    argv.append(conn.dbname)
    return argv


def _build_env(password: Optional[str]) -> dict:
    """
    Child environment. The password lives here and nowhere else — never in
    argv, so it cannot show up in `ps`, in a traceback, or in our logs.
    """
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    else:
        env.pop("PGPASSWORD", None)
    return env


def _redact(text: str) -> str:
    """Strip the database password (and its URL-encoded forms) from any text
    before it reaches a log line, an audit row, or `error_message`."""
    if not text:
        return ""
    try:
        password = _parse_database_url(get_settings().DATABASE_URL).password
    except DbDumpError:
        return text
    if not password:
        return text
    for variant in {password, urllib.parse.quote_plus(password), urllib.parse.quote(password)}:
        if variant:
            text = text.replace(variant, "***")
    return text


def _summarize_stderr(stderr: Optional[str], limit: int = 400) -> str:
    """pg_dump prints the fatal error LAST — keep that line, redact it."""
    lines = [ln.strip() for ln in (stderr or "").splitlines() if ln.strip()]
    if not lines:
        return "pg_dump failed without an error message"
    return _redact(lines[-1])[:limit]


class DbDumpResult(NamedTuple):
    returncode: int
    stderr: str
    duration_ms: int
    version: Optional[str]


def _run_pg_dump(target_path: Path) -> DbDumpResult:
    """
    Run pg_dump once. Returns a result for a completed process (returncode
    may be non-zero — the caller decides what that means) and raises
    DbDumpError for anything that prevented a process from finishing.

    This is the single seam tests monkeypatch: no test ever shells out.
    """
    settings = get_settings()
    conn = _parse_database_url(settings.DATABASE_URL)
    argv = _build_command(conn, target_path)
    env = _build_env(conn.password)

    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=settings.PG_DUMP_TIMEOUT_SECONDS,
            shell=False,
        )
    except FileNotFoundError:
        raise DbDumpError(
            f"pg_dump executable not found at '{settings.PG_DUMP_PATH}' — "
            "install the PostgreSQL client tools or set PG_DUMP_PATH"
        ) from None
    except subprocess.TimeoutExpired:
        raise DbDumpError(
            f"pg_dump timed out after {settings.PG_DUMP_TIMEOUT_SECONDS}s and was killed"
        ) from None
    duration_ms = int((time.monotonic() - started) * 1000)

    return DbDumpResult(
        returncode=proc.returncode,
        stderr=_redact(proc.stderr or ""),
        duration_ms=duration_ms,
        version=_pg_dump_version(env),
    )


def _pg_dump_version(env: dict) -> Optional[str]:
    """`pg_dump --version` — which client produced the archive (restore
    compatibility matters across major versions). Best effort only."""
    try:
        out = subprocess.run(
            [get_settings().PG_DUMP_PATH, "--version"],
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=30,
            shell=False,
        )
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()[:60] or None


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
# Database Backup Service
# ──────────────────────────────────────────────

class DbBackupService:
    """Class-based database backup service — takes a Session (module convention)."""

    def __init__(self, session: Session):
        self.session = session

    # ── Schedule settings ────────────────────────

    def get_settings(self) -> DbBackupSettingsRead:
        return DbBackupSettingsRead(
            enabled=_get_setting(self.session, DB_BACKUP_ENABLED_KEY, "true").strip().lower() == "true",
            interval_hours=max(1, _get_int_setting(self.session, DB_BACKUP_INTERVAL_KEY, DEFAULT_INTERVAL_HOURS)),
            retention_count=max(1, _get_int_setting(self.session, DB_BACKUP_RETENTION_KEY, DEFAULT_RETENTION_COUNT)),
        )

    def update_settings(self, payload: DbBackupSettingsUpdate, actor: Optional[User] = None) -> DbBackupSettingsRead:
        """Persist the schedule policy and audit the change."""
        _set_setting(self.session, DB_BACKUP_ENABLED_KEY,
                     "true" if payload.enabled else "false",
                     "PostgreSQL dump scheduler enabled")
        _set_setting(self.session, DB_BACKUP_INTERVAL_KEY,
                     str(payload.interval_hours),
                     "Hours between scheduled database dumps")
        _set_setting(self.session, DB_BACKUP_RETENTION_KEY,
                     str(payload.retention_count),
                     "Dump files kept before pruning")
        self.session.commit()

        AuditService(self.session).log_event(
            action=AuditAction.UPDATE_DB_BACKUP_SETTINGS,
            module=AuditModule.DB_BACKUPS,
            company_id=None,  # deployment-scoped
            user=actor,
            entity_name="DbBackupSettings",
            new_value=payload.model_dump(),
            description="Database backup schedule settings updated",
        )
        return self.get_settings()

    # ── Run history ──────────────────────────────

    def list_runs(self, skip: int = 0, limit: int = 50) -> Tuple[list[DbBackupRun], int]:
        """Newest first. No company filter — a dump spans every company."""
        total = self.session.exec(select(func.count(DbBackupRun.id))).one()
        rows = self.session.exec(
            select(DbBackupRun)
            .order_by(DbBackupRun.created_at.desc(), DbBackupRun.id.desc())
            .offset(skip)
            .limit(limit)
        ).all()
        return list(rows), int(total)

    def get_run(self, run_id: int) -> Optional[DbBackupRun]:
        """One run. An unknown id resolves to None → 404 upstream."""
        return self.session.get(DbBackupRun, run_id)

    def to_read(self, run: DbBackupRun) -> DbBackupRunRead:
        return DbBackupRunRead(
            id=run.id,
            status=run.status,
            trigger=run.trigger,
            triggered_by=run.triggered_by,
            triggered_by_name=self._user_name(run.triggered_by),
            started_at=run.started_at,
            finished_at=run.finished_at,
            dump_path=run.dump_path,
            dump_size_bytes=run.dump_size_bytes,
            duration_ms=run.duration_ms,
            pg_dump_version=run.pg_dump_version,
            error_message=run.error_message,
            created_at=run.created_at,
        )

    def to_reads(self, runs: list[DbBackupRun]) -> list[DbBackupRunRead]:
        """Batch the trigger-user lookup so a page of runs is one extra query,
        not one per row."""
        ids = {r.triggered_by for r in runs if r.triggered_by}
        names: dict[int, str] = {}
        if ids:
            for user in self.session.exec(select(User).where(User.id.in_(ids))).all():
                names[user.id] = user.full_name
        return [
            DbBackupRunRead(
                id=r.id,
                status=r.status,
                trigger=r.trigger,
                triggered_by=r.triggered_by,
                triggered_by_name=names.get(r.triggered_by) if r.triggered_by else None,
                started_at=r.started_at,
                finished_at=r.finished_at,
                dump_path=r.dump_path,
                dump_size_bytes=r.dump_size_bytes,
                duration_ms=r.duration_ms,
                pg_dump_version=r.pg_dump_version,
                error_message=r.error_message,
                created_at=r.created_at,
            )
            for r in runs
        ]

    def _user_name(self, user_id: Optional[int]) -> Optional[str]:
        if not user_id:
            return None
        user = self.session.get(User, user_id)
        return user.full_name if user else None

    # ── Execution ────────────────────────────────

    def run_manual_dump(self, user: User) -> DbBackupRun:
        """On-demand dump. The caller has already been verified as SUPERADMIN
        by the endpoint's `SuperAdminUser` annotation — there is deliberately
        no company resolution here (a dump spans all of them)."""
        return self.run_dump(DbBackupTrigger.MANUAL, user=user)

    def run_dump(
        self,
        trigger: DbBackupTrigger,
        user: Optional[User] = None,
    ) -> DbBackupRun:
        """
        Run one dump. Success or failure is recorded on the run row —
        failure is data, not an error response. The only HTTP error this
        raises is 409 when a dump is already in progress.
        """
        if self._any_running():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A database backup is already running",
            )

        run = DbBackupRun(
            status=DbBackupStatus.RUNNING,
            trigger=trigger,
            triggered_by=user.id if user else None,
            started_at=datetime.utcnow(),
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        try:
            self._execute(run)
        except Exception as exc:
            message = _redact(str(exc)).strip() or exc.__class__.__name__
            run.status = DbBackupStatus.FAILED
            run.finished_at = datetime.utcnow()
            run.error_message = message[:500]
            self.session.add(run)
            self.session.commit()
            AuditService(self.session).log_event(
                action=AuditAction.DB_BACKUP_FAILED,
                module=AuditModule.DB_BACKUPS,
                company_id=None,
                user=user,
                entity_name="DbBackupRun",
                entity_id=str(run.id),
                description=f"Database backup failed: {run.error_message}",
                is_success=False,
                failure_reason=run.error_message,
            )
            logger.error("Database backup failed: %s", run.error_message)
            return run

        AuditService(self.session).log_event(
            action=AuditAction.CREATE_DB_BACKUP,
            module=AuditModule.DB_BACKUPS,
            company_id=None,
            user=user,
            entity_name="DbBackupRun",
            entity_id=str(run.id),
            new_value={
                "dump_path": run.dump_path,
                "dump_size_bytes": run.dump_size_bytes,
                "duration_ms": run.duration_ms,
                "pg_dump_version": run.pg_dump_version,
                "trigger": trigger.value,
            },
            description=f"Database backup completed ({trigger.value})",
        )
        self._prune_retention()
        return run

    def _any_running(self) -> bool:
        return self.session.exec(
            select(DbBackupRun).where(DbBackupRun.status == DbBackupStatus.RUNNING)
        ).first() is not None

    # ── Download ─────────────────────────────────

    def download_path(self, run: DbBackupRun) -> Path:
        """Resolve a run's dump to an absolute path. A pruned or vanished
        file is a 404 with an explicit reason (not a bare denial)."""
        if not run.dump_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database backup no longer exists (retention policy)",
            )
        root = get_db_backup_root()
        # Stored values are POSIX; rows written on Windows hold backslashes.
        abs_path = (root / Path(run.dump_path.replace("\\", "/"))).resolve()
        try:
            abs_path.relative_to(root)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid backup path",
            )
        if not abs_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Database backup no longer exists (retention policy)",
            )
        return abs_path

    def log_download(self, run: DbBackupRun, user: Optional[User]) -> None:
        AuditService(self.session).log_event(
            action=AuditAction.DOWNLOAD_DB_BACKUP,
            module=AuditModule.DB_BACKUPS,
            company_id=None,
            user=user,
            entity_name="DbBackupRun",
            entity_id=str(run.id),
            new_value={"dump_path": run.dump_path},
            description="Database backup downloaded",
        )

    # ── Internals ────────────────────────────────

    def _execute(self, run: DbBackupRun) -> None:
        """
        Dump into `<name>.dump.part`, then `os.replace()` it into place, so
        an interrupted dump is never mistaken for a complete one — or
        downloadable as one. The `.part` file is always cleaned up.
        """
        root = get_db_backup_root()
        root.mkdir(parents=True, exist_ok=True)

        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        final_path = root / f"dms_{stamp}.dump"
        suffix = 2
        while final_path.exists():  # two runs in the same second
            final_path = root / f"dms_{stamp}_{suffix}.dump"
            suffix += 1
        part_path = root / f"{final_path.name}.part"

        try:
            result = _run_pg_dump(part_path)
            if result.returncode != 0:
                raise DbDumpError(_summarize_stderr(result.stderr))
            if not part_path.is_file():
                raise DbDumpError("pg_dump exited successfully but produced no file")
            os.replace(part_path, final_path)
        finally:
            try:
                part_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove partial dump %s", part_path.name)

        run.dump_path = final_path.relative_to(root).as_posix()
        run.dump_size_bytes = final_path.stat().st_size
        run.duration_ms = result.duration_ms
        run.pg_dump_version = result.version
        run.status = DbBackupStatus.SUCCESS
        run.finished_at = datetime.utcnow()
        self.session.add(run)
        self.session.commit()

    def _prune_retention(self) -> None:
        """
        Keep the newest `retention_count` dump files. Older FILES are
        deleted; their rows survive with dump_path = NULL so run history
        and audit remain intact.
        """
        retention = self.get_settings().retention_count
        stale_runs = self.session.exec(
            select(DbBackupRun)
            .where(DbBackupRun.dump_path.is_not(None))  # type: ignore[union-attr]
            .order_by(DbBackupRun.created_at.desc(), DbBackupRun.id.desc())
            .offset(retention)
        ).all()
        if not stale_runs:
            return

        root = get_db_backup_root()
        for run in stale_runs:
            try:
                stale = root / Path(run.dump_path.replace("\\", "/"))
                if stale.is_file():
                    stale.unlink()
            except OSError:
                logger.warning("Could not delete pruned database backup %s", run.dump_path)
            run.dump_path = None
            self.session.add(run)
        self.session.commit()


# ──────────────────────────────────────────────
# Scheduler entry point
# ──────────────────────────────────────────────

def run_due_db_backups(engine) -> int:
    """
    One scheduled pass: dump once if the newest run (any status) is older
    than the configured interval. Unlike spec 35 there is no company loop —
    one database, one run.

    A failed run counts as "recently attempted" so a persistent failure
    cannot retry-storm the worker. Opens its own session, never raises.

    Returns the number of runs started. `engine` is passed in by the caller
    (db_backups/scheduler.py binds core.database's engine at import time, so
    tests patch it there and pass the test engine straight through).
    """
    started = 0
    with Session(engine) as session:
        try:
            svc = DbBackupService(session)
            policy = svc.get_settings()
            if not policy.enabled:
                return 0
            if svc._any_running():
                return 0  # a dump is already in flight; try next tick

            now = datetime.utcnow()
            last = session.exec(
                select(DbBackupRun)
                .order_by(DbBackupRun.created_at.desc(), DbBackupRun.id.desc())
                .limit(1)
            ).first()
            if last is not None and last.created_at >= now - timedelta(hours=policy.interval_hours):
                return 0  # not due yet

            svc.run_dump(DbBackupTrigger.SCHEDULED, user=None)
            started = 1
        except Exception:
            logger.exception("Scheduled database backup pass failed")
    return started
