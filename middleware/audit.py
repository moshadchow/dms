"""
Audit Middleware
───────────────
Automatically logs significant HTTP requests to the audit trail.
Handles authentication events, document operations, and security events.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from sqlmodel import Session

from core.database import engine

logger = logging.getLogger("dms.audit")

# Paths to skip auditing (health checks, docs, etc.)
_SKIP_PATHS = ("/health", "/docs", "/redoc", "/openapi.json")

# Map of (method, path_prefix) → (AuditAction, AuditModule)
_ENDPOINT_AUDIT_MAP: list[tuple[str, str, str, str]] = [
    ("POST", "/api/v1/auth/login",          "login",              "auth"),
    ("POST", "/api/v1/auth/change-password","password_changed",   "auth"),
    ("GET",  "/api/v1/auth/azure/login",    "login",              "auth"),
    ("GET",  "/api/v1/auth/azure/callback", "login",              "auth"),
]


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def audit_middleware(request: Request, call_next: Callable) -> Response:
    path = request.url.path

    # Skip non-auditable paths
    if any(path.startswith(p) for p in _SKIP_PATHS):
        return await call_next(request)

    response: Response = await call_next(request)

    try:
        _log_request_event(request, response, path)
    except Exception:
        logger.exception("Audit middleware error")

    return response


def _log_request_event(request: Request, response: Response, path: str) -> None:
    """Create an audit event for the completed request."""
    from audit.models import AuditAction, AuditModule, AuditLog
    from audit.service import parse_user_agent
    from jose import JWTError

    status_code = response.status_code
    method = request.method
    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    # Determine if this is a security event (401/403)
    if status_code in (401, 403):
        _log_security_event(request, response, path, ip_address, user_agent, status_code)
        return

    # Check endpoint-specific audit events
    for pattern_method, pattern_path, action_str, module_str in _ENDPOINT_AUDIT_MAP:
        if method == pattern_method and path.startswith(pattern_path):
            try:
                action = AuditAction(action_str)
                module = AuditModule(module_str)
            except ValueError:
                return

            # For login, check if it was successful
            if action_str == "login" and status_code not in (200, 302):
                action = AuditAction.FAILED_LOGIN

            with Session(engine) as session:
                from audit.service import AuditService
                svc = AuditService(session)
                svc.log_event(
                    action=action,
                    module=module,
                    description=f"{method} {path} → {status_code}",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_url=str(request.url),
                    http_method=method,
                    http_status=status_code,
                    is_success=status_code < 400,
                )
            return

    # Log document operations
    if path.startswith("/api/v1/documents"):
        _log_document_event(request, response, path, method, status_code, ip_address, user_agent)


def _log_security_event(
    request: Request,
    response: Response,
    path: str,
    ip_address: str,
    user_agent: str,
    status_code: int,
) -> None:
    """Log a security event (401/403 response)."""
    from audit.models import AuditAction, AuditModule
    from audit.service import AuditService

    with Session(engine) as session:
        svc = AuditService(session)

        if status_code == 401:
            action = AuditAction.FAILED_LOGIN
            desc = f"API authentication failure: {request.method} {path}"
        else:
            action = AuditAction.PERMISSION_DENIED
            desc = f"Permission denied: {request.method} {path}"

        svc.log_event(
            action=action,
            module=AuditModule.SECURITY,
            description=desc,
            ip_address=ip_address,
            user_agent=user_agent,
            request_url=str(request.url),
            http_method=request.method,
            http_status=status_code,
            is_success=False,
            failure_reason=f"HTTP {status_code}",
        )


def _log_document_event(
    request: Request,
    response: Response,
    path: str,
    method: str,
    status_code: int,
    ip_address: str,
    user_agent: str,
) -> None:
    """Log document-related operations based on endpoint pattern."""
    from audit.models import AuditAction, AuditModule
    from audit.service import AuditService

    # Determine action from endpoint
    action = None
    entity_name = "document"

    if method == "POST" and "/upload" in path:
        action = AuditAction.UPLOAD_DOCUMENT
    elif method == "GET" and "/download" in path:
        action = AuditAction.DOWNLOAD_DOCUMENT
    elif method == "GET" and "/view" in path:
        action = AuditAction.PREVIEW_DOCUMENT
    elif method == "POST" and "/archive" in path:
        action = AuditAction.ARCHIVE_DOCUMENT
    elif method == "POST" and "/restore" in path:
        action = AuditAction.RESTORE_DOCUMENT
    elif method == "DELETE":
        action = AuditAction.DELETE_DOCUMENT
    elif method == "PATCH":
        action = AuditAction.UPDATE_DOCUMENT
    elif method == "GET" and "/workspace" in path:
        action = AuditAction.VIEW_DOCUMENT
    elif method == "GET" and path == "/api/v1/documents":
        action = AuditAction.VIEW_DOCUMENT

    if action is None:
        return

    # Extract entity ID from path
    entity_id = None
    parts = path.rstrip("/").split("/")
    for i, part in enumerate(parts):
        if part in ("documents",) and i + 1 < len(parts):
            next_part = parts[i + 1]
            if next_part.isdigit():
                entity_id = next_part
            break

    with Session(engine) as session:
        svc = AuditService(session)
        svc.log_event(
            action=action,
            module=AuditModule.DOCUMENTS,
            entity_name=entity_name,
            entity_id=entity_id,
            description=f"{method} {path} → {status_code}",
            ip_address=_get_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            request_url=str(request.url),
            http_method=method,
            http_status=status_code,
            is_success=status_code < 400,
        )
