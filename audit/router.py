import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from audit.models import AuditLogListResponse, AuditLogRead
from audit.repository import AuditRepository
from audit.service import AuditService
from core.database import get_session
from core.dependencies import AdminUser

router = APIRouter()


@router.get("", response_model=AuditLogListResponse, summary="List audit logs (Admin only)")
def list_audit_logs(
    skip:      int            = Query(0, ge=0),
    limit:     int            = Query(50, ge=1, le=200),
    start_date: Optional[datetime] = Query(None, description="Filter from date (UTC)"),
    end_date:   Optional[datetime] = Query(None, description="Filter to date (UTC)"),
    user_id:    Optional[int]  = Query(None, description="Filter by user ID"),
    module:     Optional[str]  = Query(None, description="Filter by module"),
    action:     Optional[str]  = Query(None, description="Filter by action"),
    entity_name: Optional[str] = Query(None, description="Filter by entity name"),
    entity_id:   Optional[str] = Query(None, description="Filter by entity ID"),
    role:       Optional[str]  = Query(None, description="Filter by role"),
    user_level: Optional[str]  = Query(None, description="Filter by user level"),
    auth_provider: Optional[str] = Query(None, description="Filter by auth provider"),
    ip_address: Optional[str]  = Query(None, description="Filter by IP address"),
    is_success: Optional[bool] = Query(None, description="Filter by success/failure"),
    search:     Optional[str]  = Query(None, description="Keyword search"),
    sort_by:    str            = Query("timestamp", description="Sort field"),
    sort_order: str            = Query("desc", description="Sort order: asc or desc"),
    _:          AdminUser      = None,
    session:    Session        = Depends(get_session),
):
    repo = AuditRepository(session)
    return repo.list_logs(
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        module=module,
        action=action,
        entity_name=entity_name,
        entity_id=entity_id,
        role=role,
        user_level=user_level,
        auth_provider=auth_provider,
        ip_address=ip_address,
        is_success=is_success,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{audit_id}", response_model=AuditLogRead, summary="Get audit log detail (Admin only)")
def get_audit_log(
    audit_id: int,
    _:        AdminUser = None,
    session:  Session   = Depends(get_session),
):
    repo = AuditRepository(session)
    log = repo.get_by_id(audit_id)
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Audit log {audit_id} not found")
    return AuditLogRead.model_validate(log)


@router.get("/export", summary="Export audit logs as CSV (Admin only)")
def export_audit_logs(
    start_date: Optional[datetime] = Query(None),
    end_date:   Optional[datetime] = Query(None),
    user_id:    Optional[int]      = Query(None),
    module:     Optional[str]      = Query(None),
    action:     Optional[str]      = Query(None),
    entity_name: Optional[str]     = Query(None),
    entity_id:   Optional[str]     = Query(None),
    role:       Optional[str]      = Query(None),
    user_level: Optional[str]      = Query(None),
    auth_provider: Optional[str]   = Query(None),
    ip_address: Optional[str]      = Query(None),
    is_success: Optional[bool]     = Query(None),
    search:     Optional[str]      = Query(None),
    sort_by:    str                = Query("timestamp"),
    sort_order: str                = Query("desc"),
    _:          AdminUser          = None,
    session:    Session            = Depends(get_session),
):
    repo = AuditRepository(session)
    result = repo.list_logs(
        skip=0, limit=10000,
        start_date=start_date, end_date=end_date,
        user_id=user_id, module=module, action=action,
        entity_name=entity_name, entity_id=entity_id,
        role=role, user_level=user_level, auth_provider=auth_provider,
        ip_address=ip_address, is_success=is_success, search=search,
        sort_by=sort_by, sort_order=sort_order,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Timestamp", "User ID", "Username", "Full Name", "Auth Provider",
        "Role", "User Level", "Module", "Entity Name", "Entity ID", "Action",
        "Old Value", "New Value", "Description", "IP Address", "Browser",
        "Operating System", "Device", "Request URL", "HTTP Method", "HTTP Status",
        "Session ID", "Correlation ID", "Success", "Failure Reason",
    ])
    for log in result.items:
        writer.writerow([
            log.id, log.timestamp, log.user_id, log.username, log.full_name,
            log.auth_provider, log.role, log.user_level, log.module,
            log.entity_name, log.entity_id, log.action, log.old_value,
            log.new_value, log.description, log.ip_address, log.browser,
            log.operating_system, log.device, log.request_url, log.http_method,
            log.http_status, log.session_id, log.correlation_id,
            log.is_success, log.failure_reason,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-logs.csv"},
    )
