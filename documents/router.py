from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session

from core.database import get_session
from core.dependencies import CurrentUser, require_permission
from documents.models import DocumentListResponse, DocumentRead, DocumentUpdate
from documents.service import DocumentService
from users.models import PermissionAction

router = APIRouter()


# ──────────────────────────────────────────────
# List / Search
# ──────────────────────────────────────────────

@router.get("", response_model=DocumentListResponse, summary="List / search documents")
def list_documents(
    directory_id: Optional[int] = Query(None),
    category_id:  Optional[int] = Query(None),
    file_type:    Optional[str] = Query(None, description="pdf | excel | image"),
    search:       Optional[str] = Query(None, description="Search title or filename"),
    skip:         int           = Query(0, ge=0),
    limit:        int           = Query(50, ge=1, le=200),
    current_user: CurrentUser   = None,
    session:      Session       = Depends(get_session),
):
    return DocumentService(session).list_documents(
        current_user=current_user,
        directory_id=directory_id,
        category_id=category_id,
        file_type=file_type,
        search=search,
        skip=skip,
        limit=limit,
    )


# ──────────────────────────────────────────────
# Upload
# ──────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    dependencies=[Depends(require_permission(PermissionAction.CREATE))],
)
async def upload_document(
    file:         UploadFile    = File(...),
    title:        str           = Form(..., max_length=255),
    description:  Optional[str] = Form(None),
    directory_id: int           = Form(...),
    current_user: CurrentUser   = None,
    session:      Session       = Depends(get_session),
):
    return await DocumentService(session).upload_document(
        file=file,
        title=title,
        description=description,
        directory_id=directory_id,
        uploaded_by=current_user.id,
        current_user=current_user,
    )


# ──────────────────────────────────────────────
# Single document metadata
# ──────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentRead, summary="Get document metadata")
def get_document(
    document_id:  int,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    return DocumentService(session).get_document(document_id, current_user)


# ──────────────────────────────────────────────
# View (inline browser preview)
# ──────────────────────────────────────────────

@router.get(
    "/{document_id}/view",
    summary="Preview document in browser",
    dependencies=[Depends(require_permission(PermissionAction.VIEW))],
)
def view_document(
    document_id:  int,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    abs_path, doc = DocumentService(session).get_file_path(document_id, current_user)

    def _iter(path: Path, chunk: int = 256 * 1024):
        with open(path, "rb") as f:
            while data := f.read(chunk):
                yield data

    return StreamingResponse(
        _iter(abs_path),
        media_type=doc.mime_type,
        headers={"Content-Disposition": f'inline; filename="{doc.file_name}"'},
    )


# ──────────────────────────────────────────────
# Download
# ──────────────────────────────────────────────

@router.get(
    "/{document_id}/download",
    summary="Download document",
    dependencies=[Depends(require_permission(PermissionAction.DOWNLOAD))],
)
def download_document(
    document_id:  int,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    abs_path, doc = DocumentService(session).get_file_path(document_id, current_user)
    return FileResponse(
        path=str(abs_path),
        filename=doc.file_name,
        media_type=doc.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{doc.file_name}"'},
    )


# ──────────────────────────────────────────────
# Update metadata
# ──────────────────────────────────────────────

@router.patch(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Update document metadata",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def update_document(
    document_id:  int,
    payload:      DocumentUpdate,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    return DocumentService(session).update_document(document_id, payload, current_user)


# ──────────────────────────────────────────────
# Archive / Restore
# ──────────────────────────────────────────────

@router.post(
    "/{document_id}/archive",
    response_model=DocumentRead,
    summary="Archive a document",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def archive_document(
    document_id:  int,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    return DocumentService(session).archive_document(document_id, current_user)


@router.post(
    "/{document_id}/restore",
    response_model=DocumentRead,
    summary="Restore an archived or deleted document (Admin only)",
)
def restore_document(
    document_id:  int,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    from fastapi import HTTPException
    if not current_user.is_admin():
        raise HTTPException(status_code=403, detail="Admin only")
    return DocumentService(session).restore_document(document_id, current_user)


# ──────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete document",
    dependencies=[Depends(require_permission(PermissionAction.DELETE))],
)
def delete_document(
    document_id:  int,
    hard:         bool        = Query(False, description="Permanently delete file from disk"),
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    from fastapi import HTTPException
    if hard and not current_user.is_admin():
        raise HTTPException(status_code=403, detail="Hard delete requires Admin role")
    DocumentService(session).delete_document(document_id, current_user, hard=hard)
