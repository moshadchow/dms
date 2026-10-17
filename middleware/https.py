"""
HTTPS Enforcement Middleware
────────────────────────────
Defense-in-depth for the nginx TLS edge (see dms.conf). When FORCE_HTTPS is
enabled and a request arrives with X-Forwarded-Proto: http, answer with a
308 redirect to the https equivalent of the same URL.

Contract:
  * Only acts when the X-Forwarded-Proto header is present AND equals
    "http" (first value if comma-separated). Requests without the header —
    internal /health checks, direct uvicorn access, tests — pass through
    untouched, so this never loops and never breaks local development.
  * The redirect target is built from the request itself (Host header via
    request.url) with only the scheme swapped — the hostname is never
    hardcoded here; dms.conf's return 308 handles the port-80 edge anyway.
  * Registered outermost in main.py so plain-HTTP arrivals are upgraded
    before RBAC, audit, or CORS run.
"""

from typing import Callable

from fastapi import Request
from fastapi.responses import RedirectResponse, Response

from core.config import settings


async def https_enforcement_middleware(request: Request, call_next: Callable) -> Response:
    if not settings.FORCE_HTTPS:
        return await call_next(request)

    proto = request.headers.get("x-forwarded-proto", "")
    # Multiple proxies append: take the original (first) value.
    if proto.split(",")[0].strip().lower() != "http":
        return await call_next(request)

    https_url = str(request.url.replace(scheme="https"))
    return RedirectResponse(url=https_url, status_code=308)
