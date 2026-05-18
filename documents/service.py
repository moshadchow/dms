from datetime import datetime
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from categories.models import Category
from core.access import ensure_category_access, ensure_directory_access, ensure_document_access
from directories.models import Directory
from documents.models import (
    Document,
    DocumentListResponse,
    DocumentRead,
    DocumentStatus,
    DocumentUpdate,
)
from documents.utils import delete_from_disk, resolve_storage_path, save_upload, validate_file
from users.models import User, UserCategoryLink


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

    @staticmethod
    def _to_read(doc: Document) -> DocumentRead:
        """Convert ORM object → Pydantic schema while session is still open."""
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
        )

    # ──────────────────────────────────────────
    # Public — returns Pydantic schemas only
    # ──────────────────────────────────────────

    def get_document(self, document_id: int, current_user: User) -> DocumentRead:
        return self._to_read(self._get_orm(document_id, current_user))

    def list_documents(
        self,
        current_user: User,
        directory_id: Optional[int] = None,
        category_id:  Optional[int] = None,
        file_type:    Optional[str]  = None,
        search:       Optional[str]  = None,
        skip:         int = 0,
        limit:        int = 50,
    ) -> DocumentListResponse:
        query = (
            select(Document)
            .join(Directory, Document.directory_id == Directory.id)
            .where(Document.status == DocumentStatus.ACTIVE)
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
            query = query.join_from(Directory, Category).join(
                UserCategoryLink,
                UserCategoryLink.category_id == Directory.category_id,
            ).where(
                UserCategoryLink.user_id == current_user.id,
                Category.is_active == True,
            )

            if directory_id is not None:
                ensure_directory_access(self.session, current_user, directory_id)
            if category_id is not None:
                ensure_category_access(self.session, current_user, category_id)

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

        all_docs = self.session.exec(query).all()
        total    = len(all_docs)
        page_docs = self.session.exec(
            query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
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
    ) -> DocumentRead:
        # Validate directory exists
        directory = ensure_directory_access(self.session, current_user, directory_id)

        # Validate file type
        file_type = validate_file(file)

        # Save to disk
        storage_path, file_size = await save_upload(
            file, directory.category_id, directory_id
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
        )
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)

        # Convert to Pydantic BEFORE session closes
        return self._to_read(doc)

    # ──────────────────────────────────────────
    # Update
    # ──────────────────────────────────────────

    def update_document(self, document_id: int, data: DocumentUpdate, current_user: User) -> DocumentRead:
        doc = self._get_orm(document_id, current_user)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(doc, field, value)
        doc.updated_at = datetime.utcnow()
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)
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
        return self._to_read(doc)

    def restore_document(self, document_id: int, current_user: User) -> DocumentRead:
        doc = ensure_document_access(self.session, current_user, document_id, include_deleted=True)
        doc.status = DocumentStatus.ACTIVE
        doc.updated_at = datetime.utcnow()
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)
        return self._to_read(doc)

    # ──────────────────────────────────────────
    # Delete
    # ──────────────────────────────────────────

    def delete_document(self, document_id: int, current_user: User, hard: bool = False) -> None:
        doc = self._get_orm(document_id, current_user)
        if hard:
            delete_from_disk(doc.storage_path)
            self.session.delete(doc)
        else:
            doc.status = DocumentStatus.DELETED
            doc.updated_at = datetime.utcnow()
            self.session.add(doc)
        self.session.commit()

    # ──────────────────────────────────────────
    # Download / Preview — returns ORM for streaming
    # ──────────────────────────────────────────

    def get_file_path(self, document_id: int, current_user: User):
        """
        Return (absolute_path, DocumentRead) for the router to stream.
        DocumentRead is used only for mime_type and file_name — no lazy attrs.
        """
        doc = self._get_orm(document_id, current_user)
        abs_path = resolve_storage_path(doc.storage_path)
        return abs_path, self._to_read(doc)
