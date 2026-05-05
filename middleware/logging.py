"""
Request Logging Middleware
──────────────────────────
Logs method, path, status code, and response time for every request.
"""

import time
import logging
from typing import Callable

from fastapi import Request, Response

logger = logging.getLogger("dms.access")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


async def logging_middleware(request: Request, call_next: Callable) -> Response:
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "%s %s → %d  (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
