import json
import logging
import re
from typing import Optional

from sqlmodel import Session

from audit.models import AuditAction, AuditLog, AuditModule

logger = logging.getLogger("dms.audit")


# ── User-Agent parsing ─────────────────────────

_BROWSERS = [
    (r"Edg(?:e|A|iOS)?/(\d+)", "Edge"),
    (r"OPR/(\d+)", "Opera"),
    (r"Chrome/(\d+)", "Chrome"),
    (r"Firefox/(\d+)", "Firefox"),
    (r"Safari/(\d+)", "Safari"),
    (r"MSIE (\d+)", "IE"),
    (r"Trident/.*rv:(\d+)", "IE"),
]

_OS_MAP = [
    (r"Windows NT 10\.0", "Windows 10"),
    (r"Windows NT 6\.3", "Windows 8.1"),
    (r"Windows NT 6\.2", "Windows 8"),
    (r"Windows NT 6\.1", "Windows 7"),
    (r"Mac OS X ([\d_]+)", "macOS"),
    (r"Android (\d+)", "Android"),
    (r"iPhone OS ([\d_]+)", "iOS"),
    (r"Linux", "Linux"),
]

_DEVICES = [
    (r"Mobile|Android.*Mobile|iPhone", "Mobile"),
    (r"iPad|Tablet", "Tablet"),
]


def parse_user_agent(user_agent: Optional[str]) -> dict:
    """Parse User-Agent string into browser, OS, and device."""
    result = {"browser": None, "operating_system": None, "device": None}
    if not user_agent:
        return result

    for pattern, name in _BROWSERS:
        if re.search(pattern, user_agent):
            result["browser"] = name
            break

    for pattern, name in _OS_MAP:
        match = re.search(pattern, user_agent)
        if match:
            result["operating_system"] = name
            break

    for pattern, name in _DEVICES:
        if re.search(pattern, user_agent):
            result["device"] = name
            break

    return result


# ── Audit Service ──────────────────────────────

class AuditService:
    """Centralized audit logging service.

    Uses a separate session to write audit logs, ensuring they are committed
    independently of the caller's transaction. This prevents audit loss when
    the outer transaction rolls back or the session is not committed.
    """

    def __init__(self, session):
        self.session = session

    def log_event(
        self,
        *,
        action: AuditAction,
        module: AuditModule,
        entity_name: Optional[str] = None,
        entity_id: Optional[str] = None,
        old_value: Optional[dict] = None,
        new_value: Optional[dict] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_url: Optional[str] = None,
        http_method: Optional[str] = None,
        http_status: Optional[int] = None,
        is_success: bool = True,
        failure_reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user=None,
    ) -> None:
        """Log an audit event. Never raises — failures are logged internally."""
        try:
            parsed_ua = parse_user_agent(user_agent) if user_agent else {}

            # Extract user info
            user_id = None
            username = None
            full_name = None
            auth_provider = None
            role = None
            user_level = None

            if user is not None:
                user_id = user.id
                username = getattr(user, "email", None)
                full_name = getattr(user, "full_name", None)
                auth_provider = getattr(user, "auth_provider", None)
                roles = getattr(user, "roles", [])
                if roles:
                    role = ",".join(r.name.value if hasattr(r.name, "value") else str(r.name) for r in roles)
                ul = getattr(user, "user_level", None)
                if ul:
                    user_level = ul.name

            event = AuditLog(
                user_id=user_id,
                username=username,
                full_name=full_name,
                auth_provider=auth_provider,
                role=role,
                user_level=user_level,
                module=module.value,
                entity_name=entity_name,
                entity_id=entity_id,
                action=action.value,
                old_value=json.dumps(old_value) if old_value else None,
                new_value=json.dumps(new_value) if new_value else None,
                description=description,
                ip_address=ip_address,
                browser=parsed_ua.get("browser"),
                operating_system=parsed_ua.get("operating_system"),
                device=parsed_ua.get("device"),
                request_url=request_url,
                http_method=http_method,
                http_status=http_status,
                session_id=session_id,
                correlation_id=correlation_id,
                is_success=is_success,
                failure_reason=failure_reason,
            )

            # Use a separate session to ensure audit logs are committed
            # independently of the caller's transaction
            from core.database import engine as db_engine
            with Session(db_engine) as audit_session:
                audit_session.add(event)
                audit_session.commit()
        except Exception:
            logger.exception("Failed to write audit log")
