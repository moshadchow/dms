"""Structured audit logging for authentication and security events."""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AuditEvent(str, Enum):
    LOCAL_LOGIN_SUCCESS     = "LOCAL_LOGIN_SUCCESS"
    LOCAL_LOGIN_FAILED      = "LOCAL_LOGIN_FAILED"
    AZURE_LOGIN_SUCCESS     = "AZURE_LOGIN_SUCCESS"
    AZURE_LOGIN_FAILED      = "AZURE_LOGIN_FAILED"
    AZURE_JIT_PROVISIONING  = "AZURE_JIT_PROVISIONING"
    AZURE_USER_LINKED       = "AZURE_USER_LINKED"
    AZURE_TOKEN_VALIDATION_FAILURE = "AZURE_TOKEN_VALIDATION_FAILURE"
    AZURE_TENANT_MISMATCH   = "AZURE_TENANT_MISMATCH"
    AZURE_EMAIL_MISMATCH    = "AZURE_EMAIL_MISMATCH"
    PASSWORD_CHANGED        = "PASSWORD_CHANGED"


logger = logging.getLogger("dms.audit")


def log_audit_event(
    event: AuditEvent,
    *,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    azure_oid: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    detail: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Emit a structured audit log entry."""
    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event.value,
    }
    if user_id is not None:
        entry["user_id"] = user_id
    if email is not None:
        entry["email"] = email
    if azure_oid is not None:
        entry["azure_oid"] = azure_oid
    if ip_address is not None:
        entry["ip_address"] = ip_address
    if user_agent is not None:
        entry["user_agent"] = user_agent
    if detail is not None:
        entry["detail"] = detail
    if extra is not None:
        entry.update(extra)

    logger.info(json.dumps(entry))
