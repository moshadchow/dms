from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, UploadFile, status
from sqlmodel import Session, select

from directories.models import Directory
from documents.models import (
    Document,
    DocumentCreate,
    DocumentListResponse,
    DocumentRead,
    DocumentStatus,
    DocumentUpdate,
)
from documents.utils import delete_from_disk, resolve_storage_path, save_upload, validate_file


class DocumentService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Internal — ORM fetch (session-bound)
    # ──────────────────────────────────────────

    def _get_orm(self, document_id: int) -> Document:
        """Return a session-bound ORM Document (for mutations only)."""
        doc = self.session.get(Document, document_id)
        if not doc or doc.status == DocumentStatus.DELETED:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found",
            )
        return doc

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

    def get_document(self, document_id: int) -> DocumentRead:
        return self._to_read(self._get_orm(document_id))

    def list_documents(
        self,
        directory_id: Optional[int] = None,
        category_id:  Optional[int] = None,
        file_type:    Optional[str]  = None,
        search:       Optional[str]  = None,
        skip:         int = 0,
        limit:        int = 50,
    ) -> DocumentListResponse:
        query = select(Document).where(Document.status == DocumentStatus.ACTIVE)

        if directory_id is not None:
            query = query.where(Document.directory_id == directory_id)
        if category_id is not None:
            query = query.join(Directory).where(Directory.category_id == category_id)
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
    ) -> DocumentRead:
        # Validate directory exists
        directory = self.session.get(Directory, directory_id)
        if not directory:
            raise HTTPException(
                status_code=404,
                detail=f"Directory {directory_id} not found",
            )

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

    def update_document(self, document_id: int, data: DocumentUpdate) -> DocumentRead:
        doc = self._get_orm(document_id)
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

    def archive_document(self, document_id: int) -> DocumentRead:
        doc = self._get_orm(document_id)
        doc.status = DocumentStatus.ARCHIVED
        doc.updated_at = datetime.utcnow()
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)
        return self._to_read(doc)

    def restore_document(self, document_id: int) -> DocumentRead:
        doc = self.session.get(Document, document_id)
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document {document_id} not found",
            )
        doc.status = DocumentStatus.ACTIVE
        doc.updated_at = datetime.utcnow()
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)
        return self._to_read(doc)

    # ──────────────────────────────────────────
    # Delete
    # ──────────────────────────────────────────

    def delete_document(self, document_id: int, hard: bool = False) -> None:
        doc = self._get_orm(document_id)
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

    def get_file_path(self, document_id: int):
        """
        Return (absolute_path, DocumentRead) for the router to stream.
        DocumentRead is used only for mime_type and file_name — no lazy attrs.
        """
        doc = self._get_orm(document_id)
        abs_path = resolve_storage_path(doc.storage_path)
        return abs_path, self._to_read(doc)