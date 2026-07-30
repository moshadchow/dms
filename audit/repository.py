from datetime import datetime
from typing import Optional

from sqlmodel import Session, col, select

from audit.models import AuditLog, AuditLogListResponse, AuditLogRead


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, event: AuditLog) -> AuditLog:
        self.session.add(event)
        self.session.flush()
        return event

    def get_by_id(self, audit_id: int) -> Optional[AuditLog]:
        return self.session.get(AuditLog, audit_id)

    def list_logs(
        self,
        skip: int = 0,
        limit: int = 50,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        module: Optional[str] = None,
        action: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_id: Optional[str] = None,
        role: Optional[str] = None,
        user_level: Optional[str] = None,
        auth_provider: Optional[str] = None,
        ip_address: Optional[str] = None,
        is_success: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "timestamp",
        sort_order: str = "desc",
    ) -> AuditLogListResponse:
        query = select(AuditLog)

        if start_date is not None:
            query = query.where(AuditLog.timestamp >= start_date)
        if end_date is not None:
            query = query.where(AuditLog.timestamp <= end_date)
        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
        if module is not None:
            query = query.where(AuditLog.module == module)
        if action is not None:
            query = query.where(AuditLog.action == action)
        if entity_name is not None:
            query = query.where(AuditLog.entity_name == entity_name)
        if entity_id is not None:
            query = query.where(AuditLog.entity_id == entity_id)
        if role is not None:
            query = query.where(AuditLog.role == role)
        if user_level is not None:
            query = query.where(AuditLog.user_level == user_level)
        if auth_provider is not None:
            query = query.where(AuditLog.auth_provider == auth_provider)
        if ip_address is not None:
            query = query.where(AuditLog.ip_address.ilike(f"%{ip_address}%"))
        if is_success is not None:
            query = query.where(AuditLog.is_success == is_success)
        if search:
            query = query.where(
                AuditLog.username.ilike(f"%{search}%")
                | AuditLog.full_name.ilike(f"%{search}%")
                | AuditLog.description.ilike(f"%{search}%")
                | AuditLog.entity_name.ilike(f"%{search}%")
            )

        # Count total
        from sqlmodel import func
        count_query = select(func.count()).select_from(query.subquery())
        total = self.session.exec(count_query).one()

        # Sort
        sort_column = getattr(AuditLog, sort_by, AuditLog.timestamp)
        if sort_order == "asc":
            query = query.order_by(col(sort_column).asc())
        else:
            query = query.order_by(col(sort_column).desc())

        # Paginate
        logs = self.session.exec(query.offset(skip).limit(limit)).all()

        return AuditLogListResponse(
            total=total,
            page=skip // limit + 1,
            limit=limit,
            items=[AuditLogRead.model_validate(log) for log in logs],
        )
