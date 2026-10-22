"""
Database Backup Scheduler (spec 36)
───────────────────────────────────
In-process asyncio tick loop that runs the PostgreSQL dump when it is due.
Same single-uvicorn-worker assumption as the rate limiter (spec 31) and the
folder-backup scheduler (spec 35): state is kept per process, so this only
works with one worker — which is how the app is deployed (dms-backend.service).

Independent of backups/scheduler.py on purpose: folder backups and database
dumps must be able to run, fail, or be disabled without affecting each other.

The loop is started from main.py's lifespan only when
DB_BACKUP_SCHEDULER_ENABLED is true (tests disable it via conftest, because
entering a TestClient runs lifespan). Every tick:

  1. sleep DB_BACKUP_SCHEDULER_TICK_SECONDS
  2. run_due_db_backups() in a worker thread — a dump can take minutes and
     must never block the event loop
  3. swallow + log every non-cancellation exception

This module binds `core.database.engine` at import time (same shape as
notifications/tasks.py and backups/scheduler.py) — tests/conftest.py patches
it alongside the other engine holders.
"""

import asyncio
import logging

from core.config import settings
from core.database import engine

from db_backups.service import run_due_db_backups

logger = logging.getLogger("dms.db_backups")

_task: asyncio.Task | None = None


async def _loop() -> None:
    while True:
        try:
            await asyncio.sleep(settings.DB_BACKUP_SCHEDULER_TICK_SECONDS)
            started = await asyncio.to_thread(run_due_db_backups, engine)
            if started:
                logger.info("Database backup scheduler started %d dump(s)", started)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Database backup scheduler tick failed")


def start_scheduler() -> None:
    """Start the tick loop (no-op if already running)."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop(), name="db-backup-scheduler")
        logger.info(
            "Database backup scheduler started (tick every %ds)",
            settings.DB_BACKUP_SCHEDULER_TICK_SECONDS,
        )


async def stop_scheduler() -> None:
    """Cancel the tick loop and wait for it to finish."""
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
        logger.info("Database backup scheduler stopped")
