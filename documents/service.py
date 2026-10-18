from datetime import datetime
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from categories.models import Category
from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from core.access import (
    ensure_category_access,
    ensure_category_read_access,
    ensure_directory_access,
    ensure_directory_read_access,
    ensure_document_access,
    ensure_document_user_level_access,
    expand_descendant_ids,
    get_user_category_ids,
    get_user_directory_grant_ids,
)
from directories.models import Directory
from documents.models import (
    Document,
    DocumentListResponse,
    DocumentRead,
    DocumentStatus,
    DocumentUpdate,
    DocumentUserLevelLink,
    ScanStatus,
)
from documents.utils import delete_from_disk, resolve_storage_path, save_upload, validate_file
from users.models import User
from user_levels.models import UserLevel
from company_profile.models import Company
from workflow.approval_policy import is_eligible_approver_reader
from core.config import settings

# Antivirus import (conditional to avoid circular imports)
try:
    from antivirus.service import AntivirusService
    from antivirus.engine import ScanStatus as EngineScanStatus
except ImportError:
    AntivirusService = None
    EngineScanStatus = None


class DocumentService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Internal — ORM fetch (session-bound)
    # ──────────────────────────────────────────

    def _get_orm(self, document_id: int, current_user: User, *, include_deleted: bool = False) -> Document:
        """Return a session-bound ORM Document (for mutations only)."""
        return ensure_document_access(
            self.session,
            current_user,
            document_id,
            include_deleted=include_deleted,
        )

    def _ensure_read_level_access(self, current_user: User, doc: Document) -> None:
        """User Level visibility for read paths, with the approver read-grant.

        An eligible approver at the current step of an in-flight instance may
        read the document (and attachments of memos/correspondences they are
        approving) even when User Level links exclude them — mirroring
        correspondence ``_check_view_access(approver_view=True)`` and memos
        ``_is_eligible_approver``. Mutations keep the strict guard.
        """
        try:
            ensure_document_user_level_access(self.session, current_user, doc)
        except HTTPException as exc:
            if (
                exc.status_code != 403
                or not is_eligible_approver_reader(self.session, doc.id, current_user)
            ):
                raise

    @staticmethod
    def _to_read(doc: Document) -> DocumentRead:
        """Convert ORM object → Pydantic schema while session is still open."""
        user_levels = getattr(doc, "user_levels", [])
        av_scan = getattr(doc, "av_scan", None)
        return DocumentRead(
            id=doc.id,
            title=doc.title,
            description=doc.description,
            directory_id=doc.directory_id,
            uploaded_by=doc.uploaded_by,
            file_name=doc.file_name,
            file_type=doc.file_type,
            mime_type=doc.mime_type,
            file_size=doc.file_size,
            status=doc.status,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            user_level_ids=[ul.id for ul in user_levels],
            user_level_names=[ul.name for ul in user_levels],
            av_scan_status=av_scan.scan_status if av_scan else None,
        )

    # ──────────────────────────────────────────
    # Public — returns Pydantic schemas only
    # ──────────────────────────────────────────

    def get_document(self, document_id: int, current_user: User) -> DocumentRead:
        doc = self._get_orm(document_id, current_user)
        self._ensure_read_level_access(current_user, doc)
        return self._to_read(doc)

    def list_documents(
        self,
        current_user: User,
        directory_id:    Optional[int] = None,
        category_id:     Optional[int] = None,
        file_type:       Optional[str]  = None,
        search:          Optional[str]  = None,
        status:          Optional[DocumentStatus] = None,
        # Sorting
        sort_by:         Optional[str]  = None,
        sort_order:      Optional[str]  = None,
        # Additional filters
        uploaded_by:     Optional[int]  = None,
        created_from:    Optional[datetime] = None,
        created_to:      Optional[datetime] = None,
        updated_from:    Optional[datetime] = None,
        updated_to:      Optional[datetime] = None,
        skip:            int = 0,
        limit:           int = 50,
    ) -> DocumentListResponse:
        if status is not None and status != DocumentStatus.ACTIVE and not current_user.is_admin():
            raise HTTPException(status_code=403, detail="Only admins can filter by non-active status")

        effective_status = status if status is not None else DocumentStatus.ACTIVE

        query = (
            select(Document)
            .join(Directory, Document.directory_id == Directory.id)
            .where(Document.status == effective_status)
        )

        if current_user.is_admin():
            if directory_id is not None:
                directory = self.session.get(Directory, directory_id)
                if not directory:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Directory {directory_id} not found",
                    )
            if category_id is not None:
                ensure_category_access(self.session, current_user, category_id)
        else:
            # Non-admin: category-granted categories OR granted directory
            # subtrees (descendants included). Siblings stay excluded.
            category_ids = get_user_category_ids(self.session, current_user.id)
            grant_ids = get_user_directory_grant_ids(self.session, current_user.id)
            effective_dir_ids: set = set()
            if grant_ids:
                all_dirs = list(self.session.exec(select(Directory)).all())
                effective_dir_ids = expand_descendant_ids(all_dirs, set(grant_ids))
            access_filters = []
            if category_ids:
                access_filters.append(Directory.category_id.in_(sorted(category_ids)))
            if effective_dir_ids:
                access_filters.append(Directory.id.in_(sorted(effective_dir_ids)))
            if not access_filters:
                # No grants at all: preserve the previous empty-result shape
                # without emitting `IN ()` (invalid SQL on some backends).
                query = query.where(Directory.id == -1)
            elif len(access_filters) == 1:
                query = query.join_from(Directory, Category).where(
                    access_filters[0],
                    Category.is_active == True,
                )
            else:
                query = query.join_from(Directory, Category).where(
                    (access_filters[0] | access_filters[1]),
                    Category.is_active == True,
                )

            if directory_id is not None:
                # Navigation through an ancestor directory is allowed; the
                # access_filters above still scope results to authorized rows.
                ensure_directory_read_access(self.session, current_user, directory_id)
            if category_id is not None:
                ensure_category_read_access(self.session, current_user, category_id)

        # User Level visibility filtering for non-admins
        if not current_user.is_admin():
            permitted_doc_ids = [
                link.document_id
                for link in self.session.exec(
                    select(DocumentUserLevelLink).where(
                        DocumentUserLevelLink.user_level_id == current_user.user_level_id,
                    )
                ).all()
            ]
            query = query.where(Document.id.in_(permitted_doc_ids))

        # Apply filters
        if directory_id is not None:
            query = query.where(Document.directory_id == directory_id)
        if category_id is not None:
            query = query.where(Directory.category_id == category_id)
        if file_type is not None:
            query = query.where(Document.file_type == file_type)
        if search:
            query = query.where(
                Document.title.ilike(f"%{search}%")
                | Document.file_name.ilike(f"%{search}%")
            )
        # Uploaded by filter
        if uploaded_by is not None:
            query = query.where(Document.uploaded_by == uploaded_by)
        # Date range filters
        if created_from is not None:
            query = query.where(Document.created_at >= created_from)
        if created_to is not None:
            query = query.where(Document.created_at <= created_to)
        if updated_from is not None:
            query = query.where(Document.updated_at >= updated_from)
        if updated_to is not None:
            query = query.where(Document.updated_at <= updated_to)

        # Apply sorting
        sort_field_map = {
            "title":       Document.title,
            "file_name":   Document.file_name,
            "file_size":   Document.file_size,
            "created_at":  Document.created_at,
            "updated_at":  Document.updated_at,
        }
        sort_field = sort_field_map.get(sort_by, Document.created_at)
        is_desc = sort_order == "desc"
        # Default sort order: desc for dates, asc for text/size
        if sort_order is None:
            is_desc = sort_by in ("created_at", "updated_at")

        query = query.order_by(
            sort_field.desc() if is_desc else sort_field.asc(),
            Document.id.asc(),  # Secondary sort for stable pagination
        )

        all_docs = self.session.exec(query).all()
        total    = len(all_docs)
        page_docs = self.session.exec(
            query.offset(skip).limit(limit)
        ).all()

        return DocumentListResponse(
            total=total,
            page=skip // limit + 1,
            limit=limit,
            items=[self._to_read(d) for d in page_docs],
        )

    # ──────────────────────────────────────────
    # Upload
    # ──────────────────────────────────────────

    async def upload_document(
        self,
        file:         UploadFile,
        title:        str,
        description:  Optional[str],
        directory_id: int,
        uploaded_by:  int,
        current_user: User,
        user_level_ids: Optional[list[int]] = None,
    ) -> DocumentRead:
        # Validate directory exists
        directory = ensure_directory_access(self.session, current_user, directory_id)

        # Validate user level IDs
        if not user_level_ids:
            if current_user.user_level_id:
                user_level_ids = [current_user.user_level_id]
            else:
                raise HTTPException(
                    status_code=422,
                    detail="At least one user level must be selected for document visibility",
                )

        valid_levels = self.session.exec(
            select(UserLevel).where(
                UserLevel.id.in_(user_level_ids),
                UserLevel.is_active == True,
            )
        ).all()
        valid_level_ids = {ul.id for ul in valid_levels}

        invalid_ids = set(user_level_ids) - valid_level_ids
        if invalid_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid or inactive user level IDs: {sorted(invalid_ids)}",
            )

        # Validate file type
        file_type = validate_file(file)

        # Get company from authenticated user
        company: Company = current_user.company
        if not company:
            raise HTTPException(
                status_code=400,
                detail="User must belong to a company to upload documents"
            )

        # Save to disk
        storage_path, file_size = await save_upload(
            file, directory.category_id, directory_id, company
        )

        # Antivirus scanning (if enabled)
        av_scan = None
        if settings.AV_ENABLED and AntivirusService:
            try:
                from antivirus.engine import ScanStatus as EngineScanStatus
                from core.storage import storage_service
                
                # Resolve absolute path for scanning
                abs_path = storage_service.resolve_path_with_fallback(storage_path, company)
                
                av_svc = AntivirusService(self.session)
                av_scan = await av_svc.scan_file(abs_path, storage_path, company)
                
                # Handle scan results
                if av_scan.scan_status == EngineScanStatus.INFECTED:
                    # File quarantined by scan_file, delete the document record if created
                    AuditService(self.session).log_event(
                        action=AuditAction.UPLOAD_DOCUMENT,
                        module=AuditModule.DOCUMENTS,
                        company_id=current_user.company_id,
                        entity_name="document",
                        entity_id="scan_failed",
                        new_value={"title": title, "file_name": file.filename, "threat": av_scan.threat_name},
                        description=f"Upload rejected: infected file '{title}' ({av_scan.threat_name})",
                        is_success=False,
                        failure_reason=f"Malware detected: {av_scan.threat_name}",
                        user=current_user,
                    )
                    raise HTTPException(
                        status_code=422,
                        detail=f"File rejected: malware detected ({av_scan.threat_name})",
                    )
                elif av_scan.scan_status == EngineScanStatus.TIMEOUT:
                    # Clean up file
                    from documents.utils import delete_from_disk
                    delete_from_disk(storage_path, company)
                    AuditService(self.session).log_event(
                        action=AuditAction.UPLOAD_DOCUMENT,
                        module=AuditModule.DOCUMENTS,
                        company_id=current_user.company_id,
                        entity_name="document",
                        entity_id="scan_failed",
                        new_value={"title": title, "file_name": file.filename},
                        description=f"Upload failed: scan timeout for '{title}'",
                        is_success=False,
                        failure_reason="Antivirus scan timeout",
                        user=current_user,
                    )
                    raise HTTPException(
                        status_code=504,
                        detail="Antivirus scan timeout",
                    )
                elif av_scan.scan_status == EngineScanStatus.ERROR:
                    # Clean up file
                    from documents.utils import delete_from_disk
                    delete_from_disk(storage_path, company)
                    AuditService(self.session).log_event(
                        action=AuditAction.UPLOAD_DOCUMENT,
                        module=AuditModule.DOCUMENTS,
                        company_id=current_user.company_id,
                        entity_name="document",
                        entity_id="scan_failed",
                        new_value={"title": title, "file_name": file.filename},
                        description=f"Upload failed: scan error for '{title}'",
                        is_success=False,
                        failure_reason="Antivirus scan error",
                        user=current_user,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail="Antivirus scan failed",
                    )
                # If clean, continue with document creation
            except HTTPException:
                raise
            except Exception as e:
                # Unexpected error during scanning - clean up and fail
                from documents.utils import delete_from_disk
                delete_from_disk(storage_path, company)
                AuditService(self.session).log_event(
                    action=AuditAction.UPLOAD_DOCUMENT,
                    module=AuditModule.DOCUMENTS,
                    company_id=current_user.company_id,
                    entity_name="document",
                    entity_id="scan_failed",
                    new_value={"title": title, "file_name": file.filename},
                    description=f"Upload failed: scan exception for '{title}'",
                    is_success=False,
                    failure_reason=f"Antivirus scan error: {str(e)}",
                    user=current_user,
                )
                raise HTTPException(
                    status_code=500,
                    detail="Antivirus scan failed",
                )

        doc = Document(
            title=title,
            description=description,
            directory_id=directory_id,
            uploaded_by=uploaded_by,
            file_name=file.filename or "unknown",
            file_type=file_type,
            mime_type=file.content_type or "",
            file_size=file_size,
            storage_path=storage_path,
            av_scan_id=av_scan.id if av_scan else None,
        )
        self.session.add(doc)
        self.session.flush()

        # Create user level links
        for level_id in valid_level_ids:
            self.session.add(
                DocumentUserLevelLink(document_id=doc.id, user_level_id=level_id)
            )

        self.session.commit()
        self.session.refresh(doc)

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.UPLOAD_DOCUMENT,
            module=AuditModule.DOCUMENTS,
            company_id=current_user.company_id,
            entity_name="document",
            entity_id=str(doc.id),
            new_value={"title": title, "file_name": file.filename, "av_scan_status": av_scan.scan_status.value if av_scan else "skipped"},
            description=f"Uploaded document '{title}'",
            is_success=True,
            user=current_user,
        )

        # Convert to Pydantic BEFORE session closes
        return self._to_read(doc)

    # ──────────────────────────────────────────
    # Update
    # ──────────────────────────────────────────

    def update_document(self, document_id: int, data: DocumentUpdate, current_user: User) -> DocumentRead:
        doc = self._get_orm(document_id, current_user)
        old_values = {"title": doc.title, "description": doc.description}
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(doc, field, value)
        doc.updated_at = datetime.utcnow()
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.UPDATE_DOCUMENT,
            module=AuditModule.DOCUMENTS,
            company_id=current_user.company_id,
            entity_name="document",
            entity_id=str(document_id),
            old_value=old_values,
            new_value=data.model_dump(exclude_unset=True),
            description=f"Updated document {document_id}",
            is_success=True,
            user=current_user,
        )

        return self._to_read(doc)

    # ──────────────────────────────────────────
    # Archive / Restore
    # ──────────────────────────────────────────

    def archive_document(self, document_id: int, current_user: User) -> DocumentRead:
        doc = self._get_orm(document_id, current_user)
        doc.status = DocumentStatus.ARCHIVED
        doc.updated_at = datetime.utcnow()
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.ARCHIVE_DOCUMENT,
            module=AuditModule.DOCUMENTS,
            company_id=current_user.company_id,
            entity_name="document",
            entity_id=str(document_id),
            old_value={"status": "active"},
            new_value={"status": "archived"},
            description=f"Archived document {document_id}",
            is_success=True,
            user=current_user,
        )

        return self._to_read(doc)

    def restore_document(self, document_id: int, current_user: User) -> DocumentRead:
        doc = ensure_document_access(self.session, current_user, document_id, include_deleted=True)
        old_status = doc.status.value
        doc.status = DocumentStatus.ACTIVE
        doc.updated_at = datetime.utcnow()
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.RESTORE_DOCUMENT,
            module=AuditModule.DOCUMENTS,
            company_id=current_user.company_id,
            entity_name="document",
            entity_id=str(document_id),
            old_value={"status": old_status},
            new_value={"status": "active"},
            description=f"Restored document {document_id}",
            is_success=True,
            user=current_user,
        )

        return self._to_read(doc)

    def bulk_restore_documents(self, document_ids: list[int], current_user: User) -> dict:
        if not current_user.is_admin():
            raise HTTPException(status_code=403, detail="Admin only")
        restored = []
        failed = []
        for doc_id in document_ids:
            try:
                restored.append(self.restore_document(doc_id, current_user))
            except HTTPException as exc:
                failed.append({"id": doc_id, "error": exc.detail})
            except Exception as exc:
                failed.append({"id": doc_id, "error": str(exc)})
        return {"restored": restored, "failed": failed}

    # ──────────────────────────────────────────
    # Delete
    # ──────────────────────────────────────────

    def delete_document(self, document_id: int, current_user: User, hard: bool = False) -> None:
        doc = self._get_orm(document_id, current_user)
        old_values = {"status": doc.status.value, "title": doc.title}
        if hard:
            # Determine company from document's directory -> category -> company
            company = doc.directory.category.company
            delete_from_disk(doc.storage_path, company)
            self.session.delete(doc)
        else:
            doc.status = DocumentStatus.DELETED
            doc.updated_at = datetime.utcnow()
            self.session.add(doc)
        self.session.commit()

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.DELETE_DOCUMENT,
            module=AuditModule.DOCUMENTS,
            company_id=current_user.company_id,
            entity_name="document",
            entity_id=str(document_id),
            old_value=old_values,
            new_value={"status": "deleted", "hard_delete": hard},
            description=f"{'Hard' if hard else 'Soft'} deleted document {document_id}",
            is_success=True,
            user=current_user,
        )

    # ──────────────────────────────────────────
    # Download / Preview — returns ORM for streaming
    # ──────────────────────────────────────────

    def get_file_path(self, document_id: int, current_user: User):
        """
        Return (absolute_path, DocumentRead) for the router to stream.
        DocumentRead is used only for mime_type and file_name — no lazy attrs.
        """
        doc = self._get_orm(document_id, current_user)
        self._ensure_read_level_access(current_user, doc)
        # Determine company from document's directory -> category -> company
        company = doc.directory.category.company
        abs_path = resolve_storage_path(doc.storage_path, company)
        return abs_path, self._to_read(doc)
