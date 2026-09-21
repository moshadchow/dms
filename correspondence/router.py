from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from core.database import get_session
from core.dependencies import CurrentUser, require_permission
from correspondence.models import (
    AttachmentType,
    CorrespondenceAttachment,
    CorrespondenceAttachmentRead,
    CorrespondenceDetailRead,
    CorrespondenceDirection,
    CorrespondenceListResponse,
    CorrespondenceMovementRead,
    CorrespondencePriority,
    CorrespondenceRead,
    CorrespondenceStatus,
)
from correspondence.schemas import (
    CorrespondenceArchive,
    CorrespondenceAssign,
    CorrespondenceComplete,
    CorrespondenceCreate,
    CorrespondenceDispatch,
    CorrespondenceSubmit,
    CorrespondenceUpdate,
)
from correspondence.service import CorrespondenceService
from users.models import PermissionAction

router = APIRouter()


@router.post(
    "",
    response_model=CorrespondenceDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a correspondence draft",
    dependencies=[Depends(require_permission(PermissionAction.CREATE))],
)
def create_correspondence(
    payload: CorrespondenceCreate,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).create_draft(payload, current_user)


@router.get(
    "",
    response_model=CorrespondenceListResponse,
    summary="List correspondences",
)
def list_correspondences(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    direction: Optional[CorrespondenceDirection] = None,
    priority: Optional[CorrespondencePriority] = None,
    corr_status: Optional[CorrespondenceStatus] = Query(None, alias="status"),
    category_id: Optional[int] = None,
    response_required: Optional[bool] = None,
    overdue: Optional[bool] = None,
    search: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).list_correspondences(
        current_user,
        direction=direction,
        priority=priority,
        corr_status=corr_status,
        category_id=category_id,
        response_required=response_required,
        overdue=overdue,
        search=search,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/next-reference",
    summary="Preview next reference number (non-destructive)",
)
def get_next_reference(
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return {"reference": CorrespondenceService(session).get_next_reference(current_user)}


@router.get(
    "/by-document/{document_id}",
    response_model=CorrespondenceDetailRead,
    summary="Get correspondence by document ID",
)
def get_correspondence_by_document(
    document_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).get_correspondence_by_document(document_id, current_user)


@router.get(
    "/{correspondence_id}",
    response_model=CorrespondenceDetailRead,
    summary="Get correspondence detail",
)
def get_correspondence(
    correspondence_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).get_correspondence(correspondence_id, current_user)


@router.patch(
    "/{correspondence_id}",
    response_model=CorrespondenceDetailRead,
    summary="Update a correspondence",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def update_correspondence(
    correspondence_id: int,
    payload: CorrespondenceUpdate,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).update_correspondence(correspondence_id, payload, current_user)


@router.post(
    "/{correspondence_id}/submit",
    response_model=CorrespondenceDetailRead,
    summary="Submit correspondence for workflow approval",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def submit_correspondence(
    correspondence_id: int,
    payload: CorrespondenceSubmit,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
    background_tasks: BackgroundTasks = None,
):
    return CorrespondenceService(session).submit_correspondence(
        correspondence_id, payload, current_user, background_tasks
    )


@router.post(
    "/{correspondence_id}/assign",
    response_model=CorrespondenceDetailRead,
    summary="Assign correspondence to a user",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def assign_correspondence(
    correspondence_id: int,
    payload: CorrespondenceAssign,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).assign_correspondence(correspondence_id, payload, current_user)


@router.post(
    "/{correspondence_id}/forward",
    response_model=CorrespondenceDetailRead,
    summary="Forward correspondence to a user",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def forward_correspondence(
    correspondence_id: int,
    payload: CorrespondenceAssign,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).forward_correspondence(correspondence_id, payload, current_user)


@router.post(
    "/{correspondence_id}/dispatch",
    response_model=CorrespondenceDetailRead,
    summary="Dispatch correspondence",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def dispatch_correspondence(
    correspondence_id: int,
    payload: CorrespondenceDispatch,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).dispatch_correspondence(correspondence_id, payload, current_user)


@router.post(
    "/{correspondence_id}/deliver",
    response_model=CorrespondenceDetailRead,
    summary="Mark correspondence as delivered",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def mark_delivered(
    correspondence_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).mark_delivered(correspondence_id, current_user)


@router.post(
    "/{correspondence_id}/acknowledge",
    response_model=CorrespondenceDetailRead,
    summary="Mark correspondence as acknowledged",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def mark_acknowledged(
    correspondence_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).mark_acknowledged(correspondence_id, current_user)


@router.post(
    "/{correspondence_id}/complete",
    response_model=CorrespondenceDetailRead,
    status_code=status.HTTP_200_OK,
    summary="Complete a correspondence",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def complete_correspondence(
    correspondence_id: int,
    payload: CorrespondenceComplete,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
    background_tasks: BackgroundTasks = None,
):
    return CorrespondenceService(session).complete_correspondence(
        correspondence_id, payload, current_user, background_tasks
    )


@router.post(
    "/{correspondence_id}/archive",
    response_model=CorrespondenceDetailRead,
    status_code=status.HTTP_200_OK,
    summary="Archive a correspondence",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def archive_correspondence(
    correspondence_id: int,
    payload: CorrespondenceArchive,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
    background_tasks: BackgroundTasks = None,
):
    return CorrespondenceService(session).archive_correspondence(
        correspondence_id, payload, current_user, background_tasks
    )


@router.get(
    "/{correspondence_id}/movements",
    response_model=list[CorrespondenceMovementRead],
    summary="Get movement history",
)
def get_movements(
    correspondence_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).get_movements(correspondence_id, current_user)


@router.post(
    "/{correspondence_id}/attachments",
    response_model=CorrespondenceAttachmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an attachment to correspondence",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def add_attachment(
    correspondence_id: int,
    file: UploadFile = File(...),
    attachment_type: AttachmentType = Form(AttachmentType.SUPPORTING),
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return CorrespondenceService(session).add_attachment(
        correspondence_id, file, attachment_type, current_user
    )


@router.delete(
    "/{correspondence_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an attachment from correspondence",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def remove_attachment(
    correspondence_id: int,
    attachment_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    CorrespondenceService(session).remove_attachment(correspondence_id, attachment_id, current_user)


@router.get(
    "/{correspondence_id}/attachments/{attachment_id}/download",
    summary="Download a specific attachment",
)
def download_attachment(
    correspondence_id: int,
    attachment_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    from fastapi import HTTPException
    from sqlmodel import select
    from company_profile.models import Company
    from correspondence.models import Correspondence, CorrespondenceAttachment
    from documents.utils import resolve_storage_path

    svc = CorrespondenceService(session)
    corr = svc._get_correspondence_or_404(correspondence_id)
    svc._check_view_access(corr, current_user)

    link = session.get(CorrespondenceAttachment, attachment_id)
    if not link or link.correspondence_id != correspondence_id:
        raise HTTPException(status_code=404, detail="Attachment not found")

    company = session.get(Company, corr.company_id)
    if not company:
        raise HTTPException(status_code=400, detail="Company not found")

    doc = link.document
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found for this attachment")

    abs_path = resolve_storage_path(doc.storage_path, company)
    return FileResponse(
        path=str(abs_path),
        media_type=doc.mime_type,
        filename=doc.file_name,
    )


@router.get(
    "/{correspondence_id}/download",
    summary="Download backing document file",
)
def download_document(
    correspondence_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    from fastapi import HTTPException
    from sqlmodel import select
    from company_profile.models import Company
    from correspondence.models import Correspondence
    from core.storage import storage_service
    from documents.utils import resolve_storage_path

    svc = CorrespondenceService(session)
    corr = svc._get_correspondence_or_404(correspondence_id)
    svc._check_view_access(corr, current_user)

    company = session.get(Company, corr.company_id)
    if not company:
        raise HTTPException(status_code=400, detail="Company not found")

    doc = corr.document
    if not doc:
        link = session.exec(
            select(CorrespondenceAttachment)
            .where(CorrespondenceAttachment.correspondence_id == corr.id)
            .order_by(CorrespondenceAttachment.created_at)
        ).first()
        if not link:
            raise HTTPException(status_code=404, detail="No document attached to this correspondence")
        doc = link.document

    abs_path = resolve_storage_path(doc.storage_path, company)
    return FileResponse(
        path=str(abs_path),
        media_type=doc.mime_type,
        filename=doc.file_name,
    )


@router.get(
    "/{correspondence_id}/download-final",
    summary="Download final PDF with signatures",
)
def download_final(
    correspondence_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    from fastapi import HTTPException
    from correspondence.pdf_generator import generate_correspondence_pdf

    svc = CorrespondenceService(session)
    corr = svc._get_correspondence_or_404(correspondence_id)
    svc._check_view_access(corr, current_user)

    pdf_path = generate_correspondence_pdf(session, corr, current_user)
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"{corr.reference_number}_final.pdf",
    )


@router.post(
    "/{correspondence_id}/complete",
    response_model=CorrespondenceDetailRead,
    status_code=status.HTTP_200_OK,
    summary="Complete a correspondence",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def complete_correspondence(
    correspondence_id: int,
    payload: CorrespondenceComplete,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
    background_tasks: BackgroundTasks = None,
):
    return CorrespondenceService(session).complete_correspondence(
        correspondence_id, payload, current_user, background_tasks
    )


@router.post(
    "/{correspondence_id}/archive",
    response_model=CorrespondenceDetailRead,
    status_code=status.HTTP_200_OK,
    summary="Archive a correspondence",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def archive_correspondence(
    correspondence_id: int,
    payload: Optional[dict] = None,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    from fastapi import HTTPException
    if payload is None:
        payload = {}
    return CorrespondenceService(session).archive_correspondence(
        correspondence_id,
        current_user,
        remarks=payload.get("remarks", "Correspondence archived"),
    )
