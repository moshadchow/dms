"""
RBAC Middleware
───────────────
Route-level safety net using a prefix → action map. Runs BEFORE the route
handler and catches coarse permission gaps early (missing token, wrong role).

Per-endpoint ``require_permission`` guards in ``core/dependencies.py`` are
the **authoritative** authorization layer — they declare the exact permission
each endpoint requires.  The middleware complements them by:

  1. Blocking unauthenticated / unauthorized requests before handler code runs.
  2. Catching any endpoint that forgot to add a ``require_permission`` guard.

Routes that rely on ownership checks in the service layer (e.g. document
detail, memo detail) use only ``CurrentUser`` and are intentionally NOT
mapped here — the service layer enforces the access rule.
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
    # ── Documents ─────────────────────────────
    ("GET",    "/api/v1/documents"):          PermissionAction.VIEW,
    ("POST",   "/api/v1/documents/upload"):   PermissionAction.CREATE,
    ("POST",   "/api/v1/documents"):          PermissionAction.CREATE,
    ("PUT",    "/api/v1/documents"):          PermissionAction.UPDATE,
    ("PATCH",  "/api/v1/documents"):          PermissionAction.UPDATE,
    ("DELETE", "/api/v1/documents"):          PermissionAction.DELETE,
    # ── Directories ───────────────────────────
    ("GET",    "/api/v1/directories"):         PermissionAction.VIEW,
    ("POST",   "/api/v1/directories"):        PermissionAction.CREATE,
    ("PATCH",  "/api/v1/directories"):        PermissionAction.UPDATE,
    ("DELETE", "/api/v1/directories"):        PermissionAction.DELETE,
    # ── Workflow definitions (admin config) ───
    ("POST",   "/api/v1/workflows"):          PermissionAction.CREATE,
    ("PUT",    "/api/v1/workflows"):          PermissionAction.UPDATE,
    ("PATCH",  "/api/v1/workflows"):          PermissionAction.UPDATE,
    ("DELETE", "/api/v1/workflows"):          PermissionAction.DELETE,
    # ── Workflow instances ────────────────────
    ("POST",   "/api/v1/workflow-instances"):  PermissionAction.CREATE,
    ("POST",   "/api/v1/workflow-instances/"): PermissionAction.UPDATE,
    # ── Memos ─────────────────────────────────
    ("GET",    "/api/v1/memos"):               PermissionAction.VIEW,
    ("POST",   "/api/v1/memos"):               PermissionAction.CREATE,
    ("PATCH",  "/api/v1/memos"):               PermissionAction.UPDATE,
    # ── Companies ──────────────────────────────
    ("GET",    "/api/v1/companies"):            PermissionAction.VIEW,
    ("POST",   "/api/v1/companies"):            PermissionAction.CREATE,
    ("PATCH",  "/api/v1/companies"):            PermissionAction.UPDATE,
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
    """Return the PermissionAction required for a given method + path, or None.

    Use longest matching prefix so more specific route entries override broad
    base path rules.
    """
    best_action = None
    best_prefix = ""
    for (m, prefix), action in ROUTE_PERMISSION_MAP.items():
        if m == method and path.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_action = action
    return best_action


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
