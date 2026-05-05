"""
RBAC Middleware
───────────────
Enforces route-level permission checks via a route-prefix → action map.
This acts as a secondary safety net on top of the per-endpoint
`require_permission` dependency guards.
"""

from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from jose import JWTError
from sqlmodel import Session

from core.database import engine
from core.security import verify_access_token
from users.models import PermissionAction, User

# ──────────────────────────────────────────────
# Route → required action mapping
# Key: (HTTP method, path prefix)
# Value: PermissionAction required
# ──────────────────────────────────────────────

ROUTE_PERMISSION_MAP: dict[tuple[str, str], PermissionAction] = {
    ("GET",    "/api/v1/documents"):    PermissionAction.VIEW,
    ("GET",    "/api/v1/directories"):  PermissionAction.VIEW,
    ("POST",   "/api/v1/documents"):    PermissionAction.CREATE,
    ("POST",   "/api/v1/directories"):  PermissionAction.CREATE,
    ("PUT",    "/api/v1/documents"):    PermissionAction.UPDATE,
    ("PATCH",  "/api/v1/documents"):    PermissionAction.UPDATE,
    ("DELETE", "/api/v1/documents"):    PermissionAction.DELETE,
    ("DELETE", "/api/v1/directories"):  PermissionAction.DELETE,
}

# Paths that bypass RBAC (auth endpoints, health checks, docs)
PUBLIC_PATH_PREFIXES: list[str] = [
    "/api/v1/auth",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
]


def _extract_user(token: str) -> User | None:
    """Resolve the User from a raw JWT bearer token string."""
    try:
        payload = verify_access_token(token)
        user_id = int(payload.sub)
    except (JWTError, ValueError):
        return None

    with Session(engine) as session:
        return session.get(User, user_id)


def _required_action(method: str, path: str) -> PermissionAction | None:
    """Return the PermissionAction required for a given method + path, or None."""
    for (m, prefix), action in ROUTE_PERMISSION_MAP.items():
        if m == method and path.startswith(prefix):
            return action
    return None


async def rbac_middleware(request: Request, call_next: Callable) -> Response:
    """
    Starlette-compatible middleware.
    Register in main.py:
        app.middleware("http")(rbac_middleware)
    """
    path = request.url.path

    # Skip public paths
    if any(path.startswith(p) for p in PUBLIC_PATH_PREFIXES):
        return await call_next(request)

    # Determine required permission
    action = _required_action(request.method, path)
    if action is None:
        # No mapping → allow; per-endpoint guards handle this route
        return await call_next(request)

    # Extract token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.removeprefix("Bearer ").strip()
    user  = _extract_user(token)

    if not user or not user.is_active:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Could not validate credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Admin bypasses all checks
    if user.is_admin():
        return await call_next(request)

    # Permission check
    if not user.has_permission(action):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": f"Permission denied: '{action.value}' action required"},
        )

    return await call_next(request)
