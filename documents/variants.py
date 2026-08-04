from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import Session, select

from core.config import settings
from core.access import ensure_document_access, ensure_document_user_level_access
from directories.models import Directory
from documents.models import (
    Document,
    DocumentAnnotation,
    DocumentAnnotationRead,
    DocumentAnnotationType,
    DocumentVariant,
    DocumentVariantRead,
    DocumentVariantSaveRequest,
    DocumentVariantStatus,
    DocumentVariantType,
    DrawingTool,
    DocumentWorkspaceRead,
    FileType,
)
from documents.pdf_annotations import export_annotated_pdf
from documents.utils import build_variant_storage_path, copy_into_storage, extract_docx_preview_html, extract_xlsx_preview_html, resolve_storage_path
from users.models import User


class DocumentVariantService:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _to_variant_read(variant: DocumentVariant) -> DocumentVariantRead:
        return DocumentVariantRead(
            id=variant.id,
            source_document_id=variant.source_document_id,
            owner_user_id=variant.owner_user_id,
            category_id=variant.category_id,
            directory_id=variant.directory_id,
            variant_type=variant.variant_type,
            status=variant.status,
            title=variant.title,
            source_file_name=variant.source_file_name,
            source_mime_type=variant.source_mime_type,
            file_type=variant.file_type,
            file_size=variant.file_size,
            created_at=variant.created_at,
            updated_at=variant.updated_at,
        )

    @staticmethod
    def _to_annotation_read(annotation: DocumentAnnotation) -> DocumentAnnotationRead:
        return DocumentAnnotationRead(
            id=annotation.id,
            variant_id=annotation.variant_id,
            page_number=annotation.page_number,
            annotation_type=annotation.annotation_type,
            anchor_type=annotation.anchor_type,
            drawing_tool=annotation.drawing_tool,
            thickness=annotation.thickness,
            anchor_data=annotation.anchor_data,
            note_text=annotation.note_text,
            color=annotation.color,
            created_at=annotation.created_at,
            updated_at=annotation.updated_at,
        )

    def _get_workspace_document(self, document_id: int, current_user: User) -> Document:
        doc = ensure_document_access(self.session, current_user, document_id)
        ensure_document_user_level_access(self.session, current_user, doc)
        return doc

    def _get_owned_variant(self, variant_id: int, current_user: User) -> DocumentVariant:
        variant = self.session.get(DocumentVariant, variant_id)
        if not variant or variant.status == DocumentVariantStatus.DELETED:
            raise HTTPException(status_code=404, detail=f"Document variant {variant_id} not found")

        if variant.owner_user_id != current_user.id:
            raise HTTPException(status_code=404, detail=f"Document variant {variant_id} not found")

        # Hidden unless the requester still has category access and user level access.
        doc = ensure_document_access(self.session, current_user, variant.source_document_id)
        ensure_document_user_level_access(self.session, current_user, doc)
        return variant

    def _build_preview_html(self, document: Document) -> tuple[Optional[str], Optional[str]]:
        if document.file_type == FileType.DOCX:
            try:
                return extract_docx_preview_html(resolve_storage_path(document.storage_path)), None
            except Exception as exc:
                if isinstance(exc, HTTPException):
                    return None, str(exc.detail)
                return None, "DOCX preview is unavailable for this file"

        if document.file_type == FileType.EXCEL:
            try:
                return extract_xlsx_preview_html(resolve_storage_path(document.storage_path)), None
            except Exception as exc:
                if isinstance(exc, HTTPException):
                    return None, str(exc.detail)
                return None, "Excel preview is unavailable for this file"

        return None, None

    def get_workspace(self, document_id: int, current_user: User) -> DocumentWorkspaceRead:
        document = self._get_workspace_document(document_id, current_user)
        variant = self._get_user_variant_for_document(document.id, current_user.id)
        annotations = variant.annotations if variant else []
        preview_html, preview_error = self._build_preview_html(document)

        return DocumentWorkspaceRead(
            document=self._document_read(document),
            variant=self._to_variant_read(variant) if variant else None,
            annotations=[self._to_annotation_read(annotation) for annotation in annotations],
            preview_html=preview_html,
            preview_error=preview_error,
            has_private_variant=variant is not None,
        )

    def _document_read(self, doc: Document):
        from documents.models import DocumentRead

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

    def _get_user_variant_for_document(self, document_id: int, owner_user_id: int) -> Optional[DocumentVariant]:
        return self.session.exec(
            select(DocumentVariant)
            .where(
                DocumentVariant.source_document_id == document_id,
                DocumentVariant.owner_user_id == owner_user_id,
                DocumentVariant.variant_type == DocumentVariantType.PRIVATE_ANNOTATION,
                DocumentVariant.status == DocumentVariantStatus.ACTIVE,
            )
        ).first()

    @staticmethod
    def _validate_pdf_annotation_payload(payload: DocumentVariantSaveRequest) -> None:
        for annotation in payload.annotations:
            if annotation.annotation_type != DocumentAnnotationType.STROKE:
                raise HTTPException(status_code=422, detail="PDF annotations must be saved as strokes")
            if annotation.drawing_tool not in (None, DrawingTool.PEN):
                raise HTTPException(status_code=422, detail="Only pen strokes can be saved")
            if annotation.page_number is None or annotation.page_number < 1:
                raise HTTPException(status_code=422, detail="PDF stroke annotations require a valid page number")
            if not isinstance(annotation.anchor_data.get("points"), list) or len(annotation.anchor_data["points"]) < 2:
                raise HTTPException(status_code=422, detail="Each PDF stroke must include at least two points")

    @staticmethod
    def _normalize_annotation(document: Document, annotation_payload) -> dict:
        annotation_type = annotation_payload.annotation_type
        if document.file_type == FileType.PDF:
            annotation_type = DocumentAnnotationType.STROKE

        note_text = annotation_payload.note_text
        if annotation_type == DocumentAnnotationType.STROKE:
            note_text = None

        anchor_type = annotation_payload.anchor_type
        if annotation_type == DocumentAnnotationType.STROKE:
            anchor_type = None

        return {
            "page_number": annotation_payload.page_number,
            "annotation_type": annotation_type,
            "anchor_type": anchor_type,
            "drawing_tool": annotation_payload.drawing_tool,
            "thickness": annotation_payload.thickness,
            "anchor_data": annotation_payload.anchor_data,
            "note_text": note_text,
            "color": annotation_payload.color,
        }

    def save_private_variant(
        self,
        document_id: int,
        payload: DocumentVariantSaveRequest,
        current_user: User,
    ) -> DocumentWorkspaceRead:
        document = self._get_workspace_document(document_id, current_user)
        directory = self.session.get(Directory, document.directory_id)
        if not directory:
            raise HTTPException(status_code=404, detail=f"Directory {document.directory_id} not found")
        if document.file_type == FileType.PDF:
            self._validate_pdf_annotation_payload(payload)
        variant = self._get_user_variant_for_document(document.id, current_user.id)

        if not variant:
            variant = DocumentVariant(
                source_document_id=document.id,
                owner_user_id=current_user.id,
                category_id=directory.category_id,
                directory_id=document.directory_id,
                variant_type=DocumentVariantType.PRIVATE_ANNOTATION,
                status=DocumentVariantStatus.ACTIVE,
                title=document.title,
                source_file_name=document.file_name,
                source_mime_type=document.mime_type,
                file_type=document.file_type,
                file_size=document.file_size,
                storage_path="",
            )
            self.session.add(variant)
            self.session.flush()

        storage_path = build_variant_storage_path(
            directory.category_id,
            document.directory_id,
            current_user.id,
            variant.id,
            document.file_name,
        )

        try:
            variant.category_id = directory.category_id
            variant.directory_id = document.directory_id
            variant.title = document.title
            variant.source_file_name = document.file_name
            variant.source_mime_type = document.mime_type
            variant.file_type = document.file_type
            variant.storage_path = storage_path
            variant.status = DocumentVariantStatus.ACTIVE
            variant.updated_at = datetime.utcnow()

            self.session.exec(
                delete(DocumentAnnotation).where(DocumentAnnotation.variant_id == variant.id)
            )
            self.session.flush()
            self.session.expire(variant, ["annotations"])

            normalized_annotations = [
                self._normalize_annotation(document, annotation_payload)
                for annotation_payload in payload.annotations
            ]

            for normalized in normalized_annotations:
                self.session.add(
                    DocumentAnnotation(
                        variant_id=variant.id,
                        page_number=normalized["page_number"],
                        annotation_type=normalized["annotation_type"],
                        anchor_type=normalized["anchor_type"],
                        drawing_tool=normalized["drawing_tool"],
                        thickness=normalized["thickness"],
                        anchor_data=normalized["anchor_data"],
                        note_text=normalized["note_text"],
                        color=normalized["color"],
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

            self.session.flush()
            source_path = resolve_storage_path(document.storage_path)
            storage_root = Path(settings.STORAGE_ROOT).resolve()
            variant_path = (storage_root / storage_path).resolve()
            if document.file_type == FileType.PDF:
                exported_size = export_annotated_pdf(
                    source_path,
                    variant_path,
                    self.session.exec(
                        select(DocumentAnnotation).where(DocumentAnnotation.variant_id == variant.id)
                    ).all(),
                )
            else:
                exported_size = copy_into_storage(document.storage_path, storage_path)

            variant.file_size = exported_size
            self.session.commit()
            self.session.refresh(variant)
        except Exception:
            self.session.rollback()
            try:
                path = resolve_storage_path(storage_path)
                path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

        return self.get_workspace(document_id, current_user)

    def get_variant(self, variant_id: int, current_user: User) -> DocumentVariantRead:
        variant = self._get_owned_variant(variant_id, current_user)
        return self._to_variant_read(variant)

    def get_variant_file_path(self, variant_id: int, current_user: User):
        variant = self._get_owned_variant(variant_id, current_user)
        abs_path = resolve_storage_path(variant.storage_path)
        return abs_path, self._to_variant_read(variant)
