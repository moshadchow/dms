import html
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

import bleach
from fastapi import BackgroundTasks, HTTPException, status
from sqlmodel import Session, col, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from categories.models import Category
from company_profile.models import Company
from core.access import (
    ensure_category_access,
    ensure_document_access,
    ensure_document_user_level_access,
)
from core.storage import storage_service
from correspondence.models import (
    AttachmentType,
    Correspondence,
    CorrespondenceAttachment,
    CorrespondenceDirection,
    CorrespondenceMovement,
    CorrespondencePriority,
    CorrespondenceSequence,
    CorrespondenceStatus,
    DispatchMethod,
)
from correspondence.schemas import (
    CorrespondenceArchive,
    CorrespondenceAssign,
    CorrespondenceComplete,
    CorrespondenceCreate,
    CorrespondenceDeliver,
    CorrespondenceDispatch,
    CorrespondenceSubmit,
    CorrespondenceUpdate,
)
from documents.models import Document, DocumentStatus, DocumentUserLevelLink, FileType
from documents.utils import delete_from_disk, validate_file
from directories.models import Directory
from users.models import RoleName, User, UserCategoryLink
from workflow.models import WorkflowInstance, WorkflowStatus

# Reuse memo sanitization config
ALLOWED_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "b", "em", "i", "u", "s", "strike", "del",
    "code", "pre", "blockquote",
    "ul", "ol", "li",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span", "font",
]

ALLOWED_ATTRS = {
    "*": ["class", "style", "title"],
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
    "font": ["color", "size", "face"],
}

# Terminal statuses where edits are blocked
TERMINAL_STATUSES: Set[CorrespondenceStatus] = {
    CorrespondenceStatus.APPROVED,
    CorrespondenceStatus.DISPATCHED,
    CorrespondenceStatus.DELIVERED,
    CorrespondenceStatus.ACKNOWLEDGED,
    CorrespondenceStatus.COMPLETED,
    CorrespondenceStatus.CANCELLED,
    CorrespondenceStatus.ARCHIVED,
    CorrespondenceStatus.REJECTED,
}


def sanitize_correspondence_html(body: str) -> str:
    if not body:
        return ""
    return bleach.clean(body, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


def build_correspondence_html(subject: str, body: str) -> str:
    escaped_subject = html.escape(subject)
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{escaped_subject}</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:760px;"
        "margin:2rem auto;padding:0 1.5rem;line-height:1.6;color:#1e293b}"
        "h1,h2,h3{line-height:1.25}code{background:#f1f5f9;padding:1px 5px;"
        "border-radius:4px;font-size:0.9em}pre{background:#f8fafc;padding:1rem;"
        "border:1px solid #e2e8f0;border-radius:8px;overflow-x:auto}"
        "blockquote{border-left:4px solid #cbd5e1;margin:1rem 0;padding-left:1rem;"
        "color:#64748b}table{border-collapse:collapse}td,th{border:1px solid #e2e8f0;"
        "padding:6px 10px}</style></head><body>"
        f"<h1>{escaped_subject}</h1>"
        f"{body}"
        "</body></html>"
    )


# ──────────────────────────────────────────────
# Correspondence Service
# ──────────────────────────────────────────────

class CorrespondenceService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    def _get_correspondence_or_404(self, correspondence_id: int) -> Correspondence:
        corr = self.session.get(Correspondence, correspondence_id)
        if not corr:
            raise HTTPException(status_code=404, detail=f"Correspondence {correspondence_id} not found")
        return corr

    def _check_company_access(self, correspondence: Correspondence, user: User) -> None:
        if user.is_admin():
            if any(r.name == RoleName.SUPERADMIN for r in user.roles):
                return
            if correspondence.company_id != user.company_id:
                raise HTTPException(status_code=404, detail="Correspondence not found")
            return
        if correspondence.company_id != user.company_id:
            raise HTTPException(status_code=404, detail="Correspondence not found")

    def _check_view_access(self, correspondence: Correspondence, user: User) -> None:
        self._check_company_access(correspondence, user)
        if user.is_admin():
            return
        if correspondence.document_id is not None:
            ensure_document_access(self.session, user, correspondence.document_id)

    def _check_edit_access(self, correspondence: Correspondence, user: User) -> None:
        self._check_view_access(correspondence, user)
        if correspondence.status in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot edit correspondence in '{correspondence.status.value}' status",
            )
        if correspondence.dispatch_method is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot edit correspondence after dispatch",
            )

    def _check_admin(self, user: User) -> None:
        if not user.is_admin():
            raise HTTPException(status_code=403, detail="Admin access required")

    def _resolve_company(self, user: User) -> Company:
        if not user.company_id:
            raise HTTPException(status_code=400, detail="User must belong to a company")
        company = self.session.get(Company, user.company_id)
        if not company:
            raise HTTPException(status_code=400, detail="Company not found")
        return company

    def _validate_category(self, category_id: int, company_id: int) -> None:
        cat = self.session.get(Category, category_id)
        if not cat or cat.company_id != company_id:
            raise HTTPException(status_code=422, detail="Invalid category for this company")

    def _validate_user_levels(self, level_ids: List[int]) -> Set[int]:
        from user_levels.models import UserLevel
        valid = set()
        for lid in level_ids:
            ul = self.session.get(UserLevel, lid)
            if ul and ul.is_active:
                valid.add(lid)
        return valid

    def _next_reference_number(self, company: Company) -> str:
        year = datetime.utcnow().year
        query = (
            select(CorrespondenceSequence)
            .where(
                CorrespondenceSequence.company_id == company.id,
                CorrespondenceSequence.year == year,
            )
        )
        # Use row-level locking on PostgreSQL; skip on SQLite (tests)
        try:
            from sqlalchemy.dialects.postgresql import dialect as pg_dialect
            if self.session.bind.dialect.name == "postgresql":
                query = query.with_for_update()
        except Exception:
            pass
        seq = self.session.exec(query).first()

        if seq is None:
            seq = CorrespondenceSequence(
                company_id=company.id,
                year=year,
                last_value=1,
            )
            self.session.add(seq)
            self.session.flush()
        else:
            seq.last_value += 1
            self.session.add(seq)
            self.session.flush()

        return f"COR-{company.short_name}-{year}-{seq.last_value:06d}"

    def _get_workflow_status(self, document_id: int) -> Optional[str]:
        instance = self.session.exec(
            select(WorkflowInstance)
            .where(WorkflowInstance.document_id == document_id)
            .order_by(WorkflowInstance.submitted_at.desc())
        ).first()
        return instance.status.value if instance else None

    def _save_correspondence_html(self, subject: str, body: str, user: User, company: Company) -> str:
        html_content = build_correspondence_html(subject, body)
        root = storage_service.get_company_root(company) / "correspondence" / str(user.id)
        root.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.html"
        abs_path = root / filename
        abs_path.write_text(html_content, encoding="utf-8")
        company_root = storage_service.get_company_root(company)
        return str(abs_path.relative_to(company_root))

    def _log_audit(
        self,
        action: AuditAction,
        correspondence: Correspondence,
        description: str,
        user: User,
        *,
        old_value: Optional[dict] = None,
        new_value: Optional[dict] = None,
        company_id: Optional[int] = None,
    ) -> None:
        try:
            svc = AuditService(self.session)
            svc.log_event(
                action=action,
                module=AuditModule.CORRESPONDENCE,
                company_id=company_id or correspondence.company_id,
                entity_name="correspondence",
                entity_id=str(correspondence.id),
                old_value=old_value,
                new_value=new_value,
                description=description,
                is_success=True,
                user=user,
            )
        except Exception:
            pass

    def _to_read(self, corr: Correspondence) -> "CorrespondenceRead":
        from correspondence.models import CorrespondenceRead
        return CorrespondenceRead(
            id=corr.id,
            document_id=corr.document_id,
            company_id=corr.company_id,
            created_by=corr.created_by,
            reference_number=corr.reference_number,
            direction=corr.direction,
            status=corr.status,
            subject=corr.subject,
            body=corr.body,
            priority=corr.priority,
            category_id=corr.category_id,
            sender_name=corr.sender_name,
            sender_organization=corr.sender_organization,
            recipient_name=corr.recipient_name,
            recipient_organization=corr.recipient_organization,
            date_sent=corr.date_sent,
            date_received=corr.date_received,
            response_required=corr.response_required,
            response_deadline=corr.response_deadline,
            response_received=corr.response_received,
            responded_at=corr.responded_at,
            parent_correspondence_id=corr.parent_correspondence_id,
            author_signature_id=corr.author_signature_id,
            workflow_instance_id=corr.workflow_instance_id,
            dispatch_method=corr.dispatch_method,
            dispatch_reference=corr.dispatch_reference,
            dispatched_at=corr.dispatched_at,
            delivered_at=corr.delivered_at,
            acknowledged_at=corr.acknowledged_at,
            completed_at=corr.completed_at,
            completed_by_id=corr.completed_by_id,
            archived_at=corr.archived_at,
            archived_by_id=corr.archived_by_id,
            created_by_name=corr.created_by_user.full_name if corr.created_by_user else None,
            category_name=corr.category.name if corr.category else None,
            created_at=corr.created_at,
            updated_at=corr.updated_at,
        )

    def _to_detail(self, corr: Correspondence) -> "CorrespondenceDetailRead":
        from correspondence.models import CorrespondenceAttachmentRead, CorrespondenceDetailRead, CorrespondenceMovementRead
        movements = self.session.exec(
            select(CorrespondenceMovement)
            .where(CorrespondenceMovement.correspondence_id == corr.id)
            .order_by(CorrespondenceMovement.created_at)
        ).all()

        movement_reads = []
        for m in movements:
            movement_reads.append(CorrespondenceMovementRead(
                id=m.id,
                correspondence_id=m.correspondence_id,
                from_user_id=m.from_user_id,
                from_user_name=m.from_user.full_name if m.from_user else None,
                to_user_id=m.to_user_id,
                to_user_name=m.to_user.full_name if m.to_user else None,
                from_department=m.from_department,
                to_department=m.to_department,
                action=m.action,
                remarks=m.remarks,
                created_by=m.created_by,
                created_by_name=m.actor.full_name if m.actor else None,
                created_at=m.created_at,
            ))

        attachment_reads = []
        for link in (corr.attachment_links or []):
            doc = link.document
            attachment_reads.append(CorrespondenceAttachmentRead(
                id=link.id,
                correspondence_id=link.correspondence_id,
                document_id=link.document_id,
                attachment_type=link.attachment_type,
                file_name=doc.file_name if doc else None,
                file_type=doc.file_type.value if doc and doc.file_type else None,
                mime_type=doc.mime_type if doc else None,
                file_size=doc.file_size if doc else None,
                created_by=link.created_by,
                created_by_name=link.creator.full_name if link.creator else None,
                created_at=link.created_at,
            ))

        user_level_ids = [
            link.user_level_id
            for link in self.session.exec(
                select(DocumentUserLevelLink).where(
                    DocumentUserLevelLink.document_id == corr.document_id
                )
            ).all()
        ] if corr.document_id is not None else []

        workflow_status = self._get_workflow_status(corr.document_id) if corr.document_id is not None else None
        parent_ref = corr.parent.reference_number if corr.parent else None

        return CorrespondenceDetailRead(
            id=corr.id,
            document_id=corr.document_id,
            company_id=corr.company_id,
            created_by=corr.created_by,
            reference_number=corr.reference_number,
            direction=corr.direction,
            status=corr.status,
            subject=corr.subject,
            body=corr.body,
            priority=corr.priority,
            category_id=corr.category_id,
            sender_name=corr.sender_name,
            sender_organization=corr.sender_organization,
            sender_email=corr.sender_email,
            sender_phone=corr.sender_phone,
            recipient_name=corr.recipient_name,
            recipient_organization=corr.recipient_organization,
            recipient_email=corr.recipient_email,
            recipient_phone=corr.recipient_phone,
            date_sent=corr.date_sent,
            date_received=corr.date_received,
            response_required=corr.response_required,
            response_deadline=corr.response_deadline,
            response_received=corr.response_received,
            responded_at=corr.responded_at,
            parent_correspondence_id=corr.parent_correspondence_id,
            author_signature_id=corr.author_signature_id,
            workflow_instance_id=corr.workflow_instance_id,
            dispatch_method=corr.dispatch_method,
            dispatch_reference=corr.dispatch_reference,
            dispatched_at=corr.dispatched_at,
            delivered_at=corr.delivered_at,
            acknowledged_at=corr.acknowledged_at,
            created_by_name=corr.created_by_user.full_name if corr.created_by_user else None,
            category_name=corr.category.name if corr.category else None,
            created_at=corr.created_at,
            updated_at=corr.updated_at,
            document_title=corr.document.title if corr.document else None,
            file_name=corr.document.file_name if corr.document else None,
            file_type=corr.document.file_type.value if corr.document and corr.document.file_type else None,
            mime_type=corr.document.mime_type if corr.document else None,
            file_size=corr.document.file_size if corr.document else None,
            movements=movement_reads,
            attachments=attachment_reads,
            user_level_ids=user_level_ids,
            parent_reference=parent_ref,
            workflow_status=workflow_status,
        )

    # ──────────────────────────────────────────
    # Workflow Status Sync
    # ──────────────────────────────────────────

    def _sync_workflow_status(self, corr: Correspondence) -> None:
        """Sync correspondence status from its linked workflow instance.

        Does not override post-workflow statuses (DISPATCHED, DELIVERED,
        ACKNOWLEDGED, COMPLETED, ARCHIVED) as these represent physical
        delivery lifecycle states beyond the approval workflow.
        """
        if not corr.workflow_instance_id:
            return
        instance = self.session.get(WorkflowInstance, corr.workflow_instance_id)
        if not instance:
            return

        # Post-workflow statuses should not be overridden by workflow sync
        post_workflow_statuses = {
            CorrespondenceStatus.DISPATCHED,
            CorrespondenceStatus.DELIVERED,
            CorrespondenceStatus.ACKNOWLEDGED,
            CorrespondenceStatus.COMPLETED,
            CorrespondenceStatus.ARCHIVED,
        }
        if corr.status in post_workflow_statuses:
            return

        STATUS_MAP = {
            WorkflowStatus.SUBMITTED: CorrespondenceStatus.SUBMITTED,
            WorkflowStatus.PENDING_APPROVAL: CorrespondenceStatus.PENDING_APPROVAL,
            WorkflowStatus.APPROVED: CorrespondenceStatus.APPROVED,
            WorkflowStatus.REJECTED: CorrespondenceStatus.REJECTED,
            WorkflowStatus.RETURNED: CorrespondenceStatus.RETURNED,
            WorkflowStatus.CANCELLED: CorrespondenceStatus.CANCELLED,
        }

        new_status = STATUS_MAP.get(instance.status)
        if new_status and corr.status != new_status:
            corr.status = new_status
            corr.updated_at = datetime.utcnow()
            self.session.add(corr)
            self.session.commit()

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def create_draft(self, data: CorrespondenceCreate, current_user: User) -> "CorrespondenceDetailRead":
        company = self._resolve_company(current_user)

        # Validate category
        if data.category_id is not None:
            self._validate_category(data.category_id, company.id)

        # Direction-specific validation
        if data.direction == CorrespondenceDirection.INBOUND:
            if not data.date_received:
                data.date_received = datetime.utcnow()
            if data.document_id:
                doc = self.session.get(Document, data.document_id)
                if not doc:
                    raise HTTPException(status_code=422, detail="Document not found")
        else:
            if not data.body:
                raise HTTPException(status_code=422, detail="Body is required for outbound/internal correspondence")

        # Response deadline validation
        if data.response_required and not data.response_deadline:
            raise HTTPException(status_code=422, detail="Response deadline is required when response is required")

        # Parent correspondence validation
        if data.parent_correspondence_id:
            parent = self.session.get(Correspondence, data.parent_correspondence_id)
            if not parent or parent.company_id != company.id:
                raise HTTPException(status_code=422, detail="Invalid parent correspondence")

        # Generate reference number
        ref_number = self._next_reference_number(company)

        # User levels
        if data.user_level_ids:
            valid_level_ids = self._validate_user_levels(data.user_level_ids)
        else:
            valid_level_ids = {current_user.user_level_id} if current_user.user_level_id else set()

        # Create backing document for OUTBOUND/INTERNAL
        if data.direction == CorrespondenceDirection.INBOUND:
            if data.document_id:
                doc = self.session.get(Document, data.document_id)
                document_id = doc.id
            else:
                document_id = None
        else:
            storage_path = self._save_correspondence_html(
                data.subject, sanitize_correspondence_html(data.body), current_user, company
            )
            doc = Document(
                title=data.subject,
                description=f"Correspondence: {data.subject}",
                directory_id=1,  # placeholder — correspondence doesn't use directory tree
                uploaded_by=current_user.id,
                file_name=f"{data.subject}.html",
                file_type=FileType.HTML,
                mime_type="text/html",
                file_size=len((storage_service.get_company_root(company) / storage_path).read_bytes())
                if (storage_service.get_company_root(company) / storage_path).exists() else 0,
                storage_path=storage_path,
                status=DocumentStatus.ACTIVE,
            )
            self.session.add(doc)
            self.session.flush()
            document_id = doc.id

        # Create correspondence
        now = datetime.utcnow()
        status_val = CorrespondenceStatus.RECEIVED if data.direction == CorrespondenceDirection.INBOUND else CorrespondenceStatus.DRAFT

        corr = Correspondence(
            document_id=document_id,
            company_id=company.id,
            created_by=current_user.id,
            reference_number=ref_number,
            direction=data.direction,
            status=status_val,
            subject=data.subject,
            body=sanitize_correspondence_html(data.body) if data.body else None,
            priority=data.priority,
            category_id=data.category_id,
            sender_name=data.sender_name,
            sender_organization=data.sender_organization,
            sender_email=data.sender_email,
            sender_phone=data.sender_phone,
            recipient_name=data.recipient_name,
            recipient_organization=data.recipient_organization,
            recipient_email=data.recipient_email,
            recipient_phone=data.recipient_phone,
            date_sent=None,
            date_received=data.date_received,
            response_required=data.response_required,
            response_deadline=data.response_deadline,
            parent_correspondence_id=data.parent_correspondence_id,
            author_signature_id=data.author_signature_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(corr)
        self.session.flush()

        # User level links (only when a document exists)
        if document_id is not None:
            for level_id in valid_level_ids:
                self.session.add(DocumentUserLevelLink(document_id=document_id, user_level_id=level_id))

        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.CREATE_CORRESPONDENCE,
            corr,
            f"Created correspondence '{corr.subject}'",
            current_user,
            new_value={"reference_number": corr.reference_number},
            company_id=company.id,
        )

        corr = self._get_correspondence_or_404(corr.id)
        return self._to_detail(corr)

    def get_correspondence(self, correspondence_id: int, current_user: User) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)
        self._sync_workflow_status(corr)
        return self._to_detail(corr)

    def get_correspondence_by_document(self, document_id: int, current_user: User) -> "CorrespondenceDetailRead":
        from sqlmodel import select as sqlmodel_select
        corr = self.session.exec(
            sqlmodel_select(Correspondence).where(Correspondence.document_id == document_id)
        ).first()
        if not corr:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Correspondence not found for this document")
        self._check_view_access(corr, current_user)
        self._sync_workflow_status(corr)
        return self._to_detail(corr)

    def list_correspondences(
        self,
        current_user: User,
        *,
        direction: Optional[CorrespondenceDirection] = None,
        priority: Optional[CorrespondencePriority] = None,
        corr_status: Optional[CorrespondenceStatus] = None,
        category_id: Optional[int] = None,
        assigned_user_id: Optional[int] = None,
        response_required: Optional[bool] = None,
        overdue: Optional[bool] = None,
        search: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> "CorrespondenceListResponse":
        from correspondence.models import CorrespondenceListResponse, CorrespondenceRead

        query = select(Correspondence)

        # Company scoping
        if not current_user.is_admin():
            query = query.where(Correspondence.company_id == current_user.company_id)
        elif any(r.name == RoleName.SUPERADMIN for r in current_user.roles):
            pass  # superadmin sees all
        else:
            if current_user.company_id:
                query = query.where(Correspondence.company_id == current_user.company_id)

        # Filters
        if direction:
            query = query.where(Correspondence.direction == direction)
        if priority:
            query = query.where(Correspondence.priority == priority)
        if corr_status:
            query = query.where(Correspondence.status == corr_status)
        if category_id:
            query = query.where(Correspondence.category_id == category_id)
        if response_required is not None:
            query = query.where(Correspondence.response_required == response_required)
        if date_from:
            query = query.where(Correspondence.created_at >= date_from)
        if date_to:
            query = query.where(Correspondence.created_at <= date_to)

        # Overdue filter
        if overdue is True:
            now = datetime.utcnow()
            query = query.where(
                Correspondence.response_required == True,
                Correspondence.response_received == False,
                Correspondence.response_deadline < now,
                Correspondence.status.notin_([
                    CorrespondenceStatus.COMPLETED,
                    CorrespondenceStatus.CANCELLED,
                    CorrespondenceStatus.ARCHIVED,
                    CorrespondenceStatus.REJECTED,
                ]),
            )

        # Search
        if search:
            search_term = f"%{search}%"
            query = query.where(
                (Correspondence.reference_number.ilike(search_term))
                | (Correspondence.subject.ilike(search_term))
                | (Correspondence.sender_name.ilike(search_term))
                | (Correspondence.sender_organization.ilike(search_term))
                | (Correspondence.recipient_name.ilike(search_term))
                | (Correspondence.recipient_organization.ilike(search_term))
            )

        # Count before pagination
        count_query = query
        total = len(self.session.exec(count_query).all())

        # Sort + paginate
        query = query.order_by(
            Correspondence.created_at.desc(),
            Correspondence.id.desc(),
        ).offset(skip).limit(limit)

        items = self.session.exec(query).all()

        for item in items:
            self._sync_workflow_status(item)

        return CorrespondenceListResponse(
            total=total,
            items=[self._to_read(c) for c in items],
        )

    def update_correspondence(
        self,
        correspondence_id: int,
        data: CorrespondenceUpdate,
        current_user: User,
    ) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._sync_workflow_status(corr)
        self._check_edit_access(corr, current_user)

        if data.subject is not None:
            corr.subject = data.subject
        if data.body is not None:
            corr.body = sanitize_correspondence_html(data.body)
            # Re-generate backing HTML
            company = self._resolve_company(current_user)
            if corr.document:
                old_path = corr.document.storage_path
                try:
                    delete_from_disk(old_path, company)
                except Exception:
                    pass
                new_path = self._save_correspondence_html(
                    corr.subject, corr.body, current_user, company
                )
                corr.document.storage_path = new_path
                corr.document.title = corr.subject
                corr.document.file_name = f"{corr.subject}.html"
                corr.document.updated_at = datetime.utcnow()
        if data.priority is not None:
            corr.priority = data.priority
        if data.category_id is not None:
            if data.category_id:
                self._validate_category(data.category_id, corr.company_id)
            corr.category_id = data.category_id
        if data.sender_name is not None:
            corr.sender_name = data.sender_name
        if data.sender_organization is not None:
            corr.sender_organization = data.sender_organization
        if data.sender_email is not None:
            corr.sender_email = data.sender_email
        if data.sender_phone is not None:
            corr.sender_phone = data.sender_phone
        if data.recipient_name is not None:
            corr.recipient_name = data.recipient_name
        if data.recipient_organization is not None:
            corr.recipient_organization = data.recipient_organization
        if data.recipient_email is not None:
            corr.recipient_email = data.recipient_email
        if data.recipient_phone is not None:
            corr.recipient_phone = data.recipient_phone
        if data.response_required is not None:
            corr.response_required = data.response_required
        if data.response_deadline is not None:
            corr.response_deadline = data.response_deadline
        if data.user_level_ids is not None:
            valid_level_ids = self._validate_user_levels(data.user_level_ids)
            existing_links = self.session.exec(
                select(DocumentUserLevelLink).where(
                    DocumentUserLevelLink.document_id == corr.document_id
                )
            ).all()
            for link in existing_links:
                self.session.delete(link)
            self.session.flush()
            for level_id in valid_level_ids:
                self.session.add(DocumentUserLevelLink(document_id=corr.document_id, user_level_id=level_id))
        if data.author_signature_id is not None:
            from workflow.service import SignatureService
            sig = SignatureService(self.session).validate_signature_exists(data.author_signature_id)
            if sig.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="You can only attach your own signatures")
            corr.author_signature_id = data.author_signature_id

        corr.updated_at = datetime.utcnow()
        self.session.add(corr)
        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.UPDATE_CORRESPONDENCE,
            corr,
            f"Updated correspondence '{corr.subject}'",
            current_user,
            new_value=data.model_dump(exclude_unset=True),
            company_id=corr.company_id,
        )

        corr = self._get_correspondence_or_404(corr.id)
        return self._to_detail(corr)

    def submit_correspondence(
        self,
        correspondence_id: int,
        data: CorrespondenceSubmit,
        current_user: User,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)

        # Only author or admin can submit
        if not current_user.is_admin() and corr.created_by != current_user.id:
            raise HTTPException(status_code=403, detail="Only the author can submit")

        if corr.status not in (CorrespondenceStatus.DRAFT, CorrespondenceStatus.RECEIVED, CorrespondenceStatus.RETURNED):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot submit correspondence in '{corr.status.value}' status",
            )

        # Validate signature ownership
        if data.signature_id is not None:
            from workflow.service import SignatureService
            sig = SignatureService(self.session).validate_signature_exists(data.signature_id)
            if sig.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="You can only attach your own signatures")
            corr.author_signature_id = data.signature_id

        # Auto-fallback: use first attachment if no primary document
        if corr.document_id is None:
            first_attachment = self.session.exec(
                select(CorrespondenceAttachment)
                .where(CorrespondenceAttachment.correspondence_id == corr.id)
                .order_by(CorrespondenceAttachment.id)
            ).first()
            if first_attachment:
                corr.document_id = first_attachment.document_id
                self.session.add(corr)
            else:
                raise HTTPException(
                    status_code=422,
                    detail="No document available for workflow submission. Upload an attachment first.",
                )

        # Delegate to workflow
        from workflow.schemas import WorkflowInstanceCreate
        from workflow.service import WorkflowInstanceService
        wf_instance = WorkflowInstanceService(self.session).submit_instance(
            WorkflowInstanceCreate(
                document_id=corr.document_id,
                workflow_definition_id=data.workflow_definition_id,
            ),
            current_user,
            background_tasks,
        )
        corr.workflow_instance_id = wf_instance.id

        corr.status = CorrespondenceStatus.SUBMITTED
        corr.updated_at = datetime.utcnow()
        self.session.add(corr)
        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.SUBMIT_CORRESPONDENCE,
            corr,
            f"Submitted correspondence '{corr.subject}' for approval",
            current_user,
            new_value={"workflow_definition_id": data.workflow_definition_id},
            company_id=corr.company_id,
        )

        corr = self._get_correspondence_or_404(corr.id)
        return self._to_detail(corr)

    def assign_correspondence(
        self,
        correspondence_id: int,
        data: CorrespondenceAssign,
        current_user: User,
    ) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)
        if not current_user.is_admin():
            raise HTTPException(status_code=403, detail="Admin access required for assignment")

        to_user = self.session.get(User, data.to_user_id)
        if not to_user or to_user.company_id != corr.company_id:
            raise HTTPException(status_code=422, detail="Invalid assignee for this company")

        movement = CorrespondenceMovement(
            correspondence_id=corr.id,
            to_user_id=data.to_user_id,
            action="assign",
            remarks=data.remarks,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
        )
        self.session.add(movement)

        corr.status = CorrespondenceStatus.ASSIGNED
        corr.updated_at = datetime.utcnow()
        self.session.add(corr)
        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.ASSIGN_CORRESPONDENCE,
            corr,
            f"Assigned correspondence to user {data.to_user_id}",
            current_user,
            company_id=corr.company_id,
        )

        corr = self._get_correspondence_or_404(corr.id)
        return self._to_detail(corr)

    def forward_correspondence(
        self,
        correspondence_id: int,
        data: CorrespondenceAssign,
        current_user: User,
    ) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)

        to_user = self.session.get(User, data.to_user_id)
        if not to_user or to_user.company_id != corr.company_id:
            raise HTTPException(status_code=422, detail="Invalid target user for this company")

        movement = CorrespondenceMovement(
            correspondence_id=corr.id,
            to_user_id=data.to_user_id,
            action="forward",
            remarks=data.remarks,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
        )
        self.session.add(movement)

        corr.updated_at = datetime.utcnow()
        self.session.add(corr)
        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.FORWARD_CORRESPONDENCE,
            corr,
            f"Forwarded correspondence to user {data.to_user_id}",
            current_user,
            company_id=corr.company_id,
        )

        corr = self._get_correspondence_or_404(corr.id)
        return self._to_detail(corr)

    def dispatch_correspondence(
        self,
        correspondence_id: int,
        data: CorrespondenceDispatch,
        current_user: User,
    ) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)
        if not current_user.is_admin():
            raise HTTPException(status_code=403, detail="Admin access required for dispatch")

        self._sync_workflow_status(corr)

        if corr.status not in (CorrespondenceStatus.APPROVED, CorrespondenceStatus.READY_FOR_DISPATCH):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot dispatch correspondence in '{corr.status.value}' status",
            )

        if corr.dispatch_method is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Correspondence has already been dispatched",
            )

        now = datetime.utcnow()
        corr.dispatch_method = data.dispatch_method
        corr.dispatch_reference = data.dispatch_reference
        corr.dispatched_at = now
        corr.date_sent = now
        corr.status = CorrespondenceStatus.DISPATCHED
        corr.updated_at = now

        movement = CorrespondenceMovement(
            correspondence_id=corr.id,
            action="dispatch",
            remarks=data.remarks or f"Dispatched via {data.dispatch_method.value}",
            created_by=current_user.id,
            created_at=now,
        )
        self.session.add(movement)
        self.session.add(corr)
        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.DISPATCH_CORRESPONDENCE,
            corr,
            f"Dispatched correspondence via {data.dispatch_method.value}",
            current_user,
            new_value={"dispatch_method": data.dispatch_method.value, "dispatch_reference": data.dispatch_reference},
            company_id=corr.company_id,
        )

        corr = self._get_correspondence_or_404(corr.id)
        return self._to_detail(corr)

    def mark_delivered(
        self,
        correspondence_id: int,
        current_user: User,
    ) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)
        if not current_user.is_admin():
            raise HTTPException(status_code=403, detail="Admin access required")

        if corr.status != CorrespondenceStatus.DISPATCHED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot mark as delivered in '{corr.status.value}' status",
            )

        now = datetime.utcnow()
        corr.delivered_at = now
        corr.status = CorrespondenceStatus.DELIVERED
        corr.updated_at = now

        movement = CorrespondenceMovement(
            correspondence_id=corr.id,
            action="delivered",
            remarks="Marked as delivered",
            created_by=current_user.id,
            created_at=now,
        )
        self.session.add(movement)
        self.session.add(corr)
        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.DELIVER_CORRESPONDENCE,
            corr,
            f"Marked correspondence '{corr.subject}' as delivered",
            current_user,
            company_id=corr.company_id,
        )

        corr = self._get_correspondence_or_404(corr.id)
        return self._to_detail(corr)

    def mark_acknowledged(
        self,
        correspondence_id: int,
        current_user: User,
    ) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)
        if not current_user.is_admin():
            raise HTTPException(status_code=403, detail="Admin access required")

        if corr.status != CorrespondenceStatus.DELIVERED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot acknowledge in '{corr.status.value}' status",
            )

        now = datetime.utcnow()
        corr.acknowledged_at = now
        corr.status = CorrespondenceStatus.ACKNOWLEDGED
        corr.updated_at = now

        movement = CorrespondenceMovement(
            correspondence_id=corr.id,
            action="acknowledged",
            remarks="Marked as acknowledged",
            created_by=current_user.id,
            created_at=now,
        )
        self.session.add(movement)
        self.session.add(corr)
        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.ACKNOWLEDGE_CORRESPONDENCE,
            corr,
            f"Marked correspondence '{corr.subject}' as acknowledged",
            current_user,
            company_id=corr.company_id,
        )

        corr = self._get_correspondence_or_404(corr.id)
        return self._to_detail(corr)

    def get_movements(self, correspondence_id: int, current_user: User) -> List["CorrespondenceMovementRead"]:
        from correspondence.models import CorrespondenceMovementRead
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)

        movements = self.session.exec(
            select(CorrespondenceMovement)
            .where(CorrespondenceMovement.correspondence_id == correspondence_id)
            .order_by(CorrespondenceMovement.created_at)
        ).all()

        return [
            CorrespondenceMovementRead(
                id=m.id,
                correspondence_id=m.correspondence_id,
                from_user_id=m.from_user_id,
                from_user_name=m.from_user.full_name if m.from_user else None,
                to_user_id=m.to_user_id,
                to_user_name=m.to_user.full_name if m.to_user else None,
                from_department=m.from_department,
                to_department=m.to_department,
                action=m.action,
                remarks=m.remarks,
                created_by=m.created_by,
                created_by_name=m.actor.full_name if m.actor else None,
                created_at=m.created_at,
            )
            for m in movements
        ]

    # ──────────────────────────────────────────
    # Attachments
    # ──────────────────────────────────────────

    def add_attachment(
        self,
        correspondence_id: int,
        file: "UploadFile",
        attachment_type: AttachmentType,
        current_user: User,
    ) -> "CorrespondenceAttachmentRead":
        from fastapi import UploadFile
        from correspondence.models import CorrespondenceAttachmentRead

        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_edit_access(corr, current_user)

        company = self._resolve_company(current_user)

        file_type = validate_file(file)

        content = file.file.read()
        file.file.seek(0)

        cat_id = corr.category_id
        if not cat_id:
            raise HTTPException(status_code=422, detail="Correspondence must have a category to upload attachments")

        directory = self.session.exec(
            select(Directory).where(Directory.category_id == cat_id)
        ).first()
        if not directory:
            raise HTTPException(status_code=422, detail="No directory found for the correspondence category")

        uploads_root = storage_service.get_uploads_root(company)
        dest_dir = uploads_root / str(cat_id) / str(directory.id)
        dest_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'upload').name}"
        dest_path = dest_dir / safe_name
        dest_path.write_bytes(content)

        storage_path = str(dest_path.relative_to(storage_service.get_company_root(company)))
        file_size = len(content)

        doc = Document(
            title=file.filename or "attachment",
            description=f"Attachment for {corr.reference_number}",
            directory_id=directory.id,
            uploaded_by=current_user.id,
            file_name=file.filename or "unknown",
            file_type=file_type,
            mime_type=file.content_type or "",
            file_size=file_size,
            storage_path=storage_path,
            status=DocumentStatus.ACTIVE,
        )
        self.session.add(doc)
        self.session.flush()

        # Copy user level links from correspondence's existing document,
        # or fall back to the uploader's user level
        if corr.document_id is not None:
            existing_links = self.session.exec(
                select(DocumentUserLevelLink).where(
                    DocumentUserLevelLink.document_id == corr.document_id
                )
            ).all()
            for link_record in existing_links:
                self.session.add(DocumentUserLevelLink(document_id=doc.id, user_level_id=link_record.user_level_id))
        elif current_user.user_level_id is not None:
            self.session.add(DocumentUserLevelLink(document_id=doc.id, user_level_id=current_user.user_level_id))

        link = CorrespondenceAttachment(
            correspondence_id=corr.id,
            document_id=doc.id,
            attachment_type=attachment_type,
            created_by=current_user.id,
        )
        self.session.add(link)
        self.session.commit()
        self.session.refresh(link)

        self._log_audit(
            AuditAction.CREATE_CORRESPONDENCE,
            corr,
            f"Added attachment '{file.filename}' to correspondence '{corr.reference_number}'",
            current_user,
            new_value={"attachment_id": link.id, "document_id": doc.id},
            company_id=corr.company_id,
        )

        return CorrespondenceAttachmentRead(
            id=link.id,
            correspondence_id=link.correspondence_id,
            document_id=link.document_id,
            attachment_type=link.attachment_type,
            file_name=doc.file_name,
            file_type=doc.file_type.value if doc.file_type else None,
            mime_type=doc.mime_type,
            file_size=doc.file_size,
            created_by=link.created_by,
            created_by_name=current_user.full_name,
            created_at=link.created_at,
        )

    def remove_attachment(
        self,
        correspondence_id: int,
        attachment_id: int,
        current_user: User,
    ) -> None:
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_edit_access(corr, current_user)

        link = self.session.get(CorrespondenceAttachment, attachment_id)
        if not link or link.correspondence_id != corr.id:
            raise HTTPException(status_code=404, detail="Attachment not found")

        doc = self.session.get(Document, link.document_id)
        if doc:
            company = self._resolve_company(current_user)
            try:
                delete_from_disk(doc.storage_path, company)
            except Exception:
                pass
            doc.status = DocumentStatus.DELETED
            doc.updated_at = datetime.utcnow()
            self.session.add(doc)

        self.session.delete(link)
        self.session.commit()

        self._log_audit(
            AuditAction.UPDATE_CORRESPONDENCE,
            corr,
            f"Removed attachment from correspondence '{corr.reference_number}'",
            current_user,
            new_value={"attachment_id": attachment_id},
            company_id=corr.company_id,
        )

    def complete_correspondence(
        self,
        correspondence_id: int,
        data: CorrespondenceComplete,
        current_user: User,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)
        self._sync_workflow_status(corr)

        if corr.status != CorrespondenceStatus.ACKNOWLEDGED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot complete correspondence in "
                    f"'{corr.status.value}' status"
                ),
            )

        now = datetime.utcnow()
        corr.status = CorrespondenceStatus.COMPLETED
        corr.completed_at = now
        corr.completed_by_id = current_user.id
        corr.updated_at = now
        self.session.add(
            CorrespondenceMovement(
                correspondence_id=corr.id,
                action="complete",
                remarks=data.remarks or "Correspondence completed",
                created_by=current_user.id,
                created_at=now,
            )
        )
        self.session.add(corr)
        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.COMPLETE_CORRESPONDENCE,
            corr,
            f"Completed correspondence '{corr.reference_number}'",
            current_user,
            company_id=corr.company_id,
        )

        # Trigger notification for completion
        if background_tasks:
            background_tasks.add_task(
                send_notification_task,
                notification_type="correspondence_completed",
                instance_id=corr.workflow_instance_id or 0,
                document_id=corr.document_id,
                step_order=None,
            )
        return self._to_read(corr)

    def archive_correspondence(
        self,
        correspondence_id: int,
        data: CorrespondenceArchive,
        current_user: User,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> "CorrespondenceDetailRead":
        corr = self._get_correspondence_or_404(correspondence_id)
        self._check_view_access(corr, current_user)
        self._sync_workflow_status(corr)

        if corr.status != CorrespondenceStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot archive correspondence in "
                    f"'{corr.status.value}' status"
                ),
            )

        now = datetime.utcnow()
        corr.status = CorrespondenceStatus.ARCHIVED
        corr.archived_at = now
        corr.archived_by_id = current_user.id
        corr.updated_at = now
        self.session.add(
            CorrespondenceMovement(
                correspondence_id=corr.id,
                action="archive",
                remarks=data.remarks or "Correspondence archived",
                created_by=current_user.id,
                created_at=now,
            )
        )
        self.session.add(corr)
        self.session.commit()
        self.session.refresh(corr)

        self._log_audit(
            AuditAction.ARCHIVE_CORRESPONDENCE,
            corr,
            f"Archived correspondence '{corr.reference_number}'",
            current_user,
            company_id=corr.company_id,
        )

        # Trigger notification for archive
        if background_tasks:
            background_tasks.add_task(
                send_notification_task,
                notification_type="correspondence_archived",
                instance_id=corr.workflow_instance_id or 0,
                document_id=corr.document_id,
                step_order=None,
            )
        return self._to_read(corr)

    def get_next_reference(self, current_user: User) -> str:
        company = self._resolve_company(current_user)
        year = datetime.utcnow().year
        seq = self.session.exec(
            select(CorrespondenceSequence).where(
                CorrespondenceSequence.company_id == company.id,
                CorrespondenceSequence.year == year,
            )
        ).first()
        next_val = (seq.last_value + 1) if seq else 1
        return f"COR-{company.short_name}-{year}-{next_val:06d}"
