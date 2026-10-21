"""
Backup Scheduler (spec 35)
──────────────────────────
In-process asyncio tick loop that runs due company backups. Same
single-uvicorn-worker assumption as the rate limiter (spec 31): state is
kept per process, so this only works with one worker — which is how the
app is deployed (dms-backend.service).

The loop is started from main.py's lifespan only when
BACKUP_SCHEDULER_ENABLED is true (tests disable it via conftest, because
entering a TestClient runs lifespan). Every tick:

  1. sleep BACKUP_SCHEDULER_TICK_SECONDS
  2. run_due_backups() in a worker thread — zip work must never block
     the event loop
  3. swallow + log every non-cancellation exception

This module binds `core.database.engine` at import time (same shape as
notifications/tasks.py) — tests/conftest.py patches it alongside the
other engine holders.
"""

import asyncio
import logging

from core.config import settings
from core.database import engine

from backups.service import run_due_backups

logger = logging.getLogger("dms.backups")

_task: asyncio.Task | None = None


async def _loop() -> None:
    while True:
        try:
            await asyncio.sleep(settings.BACKUP_SCHEDULER_TICK_SECONDS)
            started = await asyncio.to_thread(run_due_backups, engine)
            if started:
                logger.info("Backup scheduler started %d scheduled run(s)", started)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Backup scheduler tick failed")


def start_scheduler() -> None:
    """Start the tick loop (no-op if already running)."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop(), name="backup-scheduler")
        logger.info(
            "Backup scheduler started (tick every %ds)",
            settings.BACKUP_SCHEDULER_TICK_SECONDS,
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
        logger.info("Backup scheduler stopped")
