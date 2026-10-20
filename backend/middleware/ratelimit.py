"""
Rate Limiting Middleware
────────────────────────
Per-IP token buckets that reject request floods with 429 + Retry-After before
any RBAC/audit/DB work runs (spec 31). nginx adds a matching edge filter
(limit_req) in dms.conf; this is the application-level second filter.

Contract:
  * Two rules: "auth" for /api/v1/auth/login (RATE_LIMIT_AUTH_REQUESTS per
    window, per IP — brute-force protection) and "default" for everything else
    under /api/v1 (RATE_LIMIT_REQUESTS per window, per IP).
  * Skips OPTIONS, paths outside /api/v1 (/health, /docs, /redoc,
    /openapi.json live outside it), and everything when RATE_LIMIT_ENABLED is
    false (tests/conftest.py disables it by default so the suite's bursts from
    one TestClient IP never self-throttle).
  * Client IP: X-Real-IP first — nginx's proxy_set_header overwrites whatever
    the client sent, so it cannot be spoofed through the proxy. Then the LAST
    value of X-Forwarded-For: nginx appends the real IP to whatever the client
    sent ($proxy_add_x_forwarded_for), so the first value is client-controlled
    and would make throttling trivially bypassable (the audit helper's
    first-value rule is fine for forensics, not for enforcement). Fallback to
    the direct peer address.
  * State is in-process only (production runs a single uvicorn worker) and
    never touches the database: rejections are logged with the dms.ratelimit
    logger, never via AuditService — DB writes during a flood are exactly what
    this defends against. The audit middleware runs inside this limiter, so
    429s do not reach it either.
  * Memory: buckets are pruned once RATE_LIMIT_MAX_KEYS client IPs are
    tracked; if the store is still full of live buckets it is cleared
    (fail-open — throttling under memory pressure must not block users).
  * Registered between HTTPS enforcement and audit in main.py; CORS sits
    outermost so this 429 reaches the browser with CORS headers.
"""

import logging
import math
import threading
import time
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from core.config import settings

logger = logging.getLogger("dms.ratelimit")

# Outside /api/v1 these are redundant with the prefix check, but they document
# the contract (same list as the audit middleware's skip set).
_SKIP_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json")

_API_PREFIX = "/api/v1"
_AUTH_LOGIN_PREFIX = "/api/v1/auth/login"


def _now() -> float:
    """Monotonic clock (module-level wrapper so tests can fake time)."""
    return time.monotonic()


class Limiter:
    """Token buckets keyed by (rule, client IP), thread-safe and in-process.

    Each bucket has capacity = rule limit and refills at limit / window
    tokens per second; a request consumes one token. Buckets store
    (tokens, updated, expires_at) where expires_at = updated + window is a
    safe upper bound on full refill — used to prune under the key cap.
    """

    def __init__(self) -> None:
        self._buckets: dict[tuple[str, str], tuple[float, float, float]] = {}
        self._lock = threading.Lock()

    def allow(
        self,
        rule: str,
        key: str,
        limit: int,
        window: int,
        max_keys: int,
        now: float | None = None,
    ) -> tuple[bool, int]:
        """Consume one token for (rule, key).

        Returns (allowed, retry_after_seconds). retry_after is 0 when allowed,
        otherwise whole seconds until one token is available (min 1).
        """
        if now is None:
            now = _now()
        refill_rate = limit / window  # tokens per second
        store_key = (rule, key)

        with self._lock:
            bucket = self._buckets.get(store_key)
            if bucket is None:
                if len(self._buckets) >= max_keys:
                    self._prune(now, max_keys)
                tokens = float(limit)
            else:
                tokens, updated, _ = bucket
                tokens = min(float(limit), tokens + (now - updated) * refill_rate)

            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[store_key] = (tokens, now, now + window)
                return True, 0

            self._buckets[store_key] = (tokens, now, now + window)
            retry_after = max(1, math.ceil((1.0 - tokens) / refill_rate))
            return False, retry_after

    def _prune(self, now: float, max_keys: int) -> None:
        expired = [
            k
            for k, (_, _, expires_at) in self._buckets.items()
            if now >= expires_at
        ]
        for k in expired:
            del self._buckets[k]
        if len(self._buckets) >= max_keys:
            # Only live buckets left and we are still at the cap — fail open.
            self._buckets.clear()

    def reset(self) -> None:
        """Drop all state (test helper)."""
        with self._lock:
            self._buckets.clear()


# Module singleton — one limiter for the process.
limiter = Limiter()


def _client_ip(request: Request) -> str:
    real = request.headers.get("x-real-ip", "").strip()
    if real:
        return real
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _rule_for(path: str) -> str:
    if path.startswith(_AUTH_LOGIN_PREFIX):
        return "auth"
    return "default"


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return await call_next(request)
    if not path.startswith(_API_PREFIX):
        return await call_next(request)

    rule = _rule_for(path)
    limit = (
        settings.RATE_LIMIT_AUTH_REQUESTS
        if rule == "auth"
        else settings.RATE_LIMIT_REQUESTS
    )
    window = settings.RATE_LIMIT_WINDOW_SECONDS
    if limit <= 0 or window <= 0:
        return await call_next(request)  # misconfig must not 500 or block all

    ip = _client_ip(request)
    allowed, retry_after = limiter.allow(
        rule=rule,
        key=ip,
        limit=limit,
        window=window,
        max_keys=settings.RATE_LIMIT_MAX_KEYS,
    )
    if allowed:
        return await call_next(request)

    logger.warning(
        "rate limited %s %s rule=%s ip=%s retry=%ss",
        request.method,
        path,
        rule,
        ip,
        retry_after,
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Too many requests. Please retry after {retry_after} seconds."
        },
        headers={"Retry-After": str(retry_after)},
    )
