from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from core.database import get_session
from core.dependencies import CurrentUser, require_permission
from memos.models import MemoDetailRead, MemoListResponse
from memos.schemas import MemoCreate, MemoSubmit, MemoUpdate
from memos.service import MemoService
from users.models import PermissionAction

router = APIRouter()


@router.post(
    "",
    response_model=MemoDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a memo draft",
    dependencies=[Depends(require_permission(PermissionAction.CREATE))],
)
def create_memo(
    payload: MemoCreate,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return MemoService(session).create_draft(payload, current_user)


@router.get(
    "",
    response_model=MemoListResponse,
    summary="List memos (author's own; admin sees all)",
)
def list_memos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return MemoService(session).list_memos(current_user, skip=skip, limit=limit)


@router.get(
    "/by-document/{document_id}",
    response_model=MemoDetailRead,
    summary="Resolve memo for a backing document",
)
def get_memo_by_document(
    document_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return MemoService(session).get_by_document(document_id, current_user)


@router.get(
    "/{memo_id}",
    response_model=MemoDetailRead,
    summary="Get memo detail",
)
def get_memo(
    memo_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return MemoService(session).get_memo(memo_id, current_user)


@router.patch(
    "/{memo_id}",
    response_model=MemoDetailRead,
    summary="Update a memo draft (author or eligible approver)",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def update_memo(
    memo_id: int,
    payload: MemoUpdate,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return MemoService(session).update_memo(memo_id, payload, current_user)


@router.post(
    "/{memo_id}/submit",
    response_model=MemoDetailRead,
    summary="Submit a memo for approval",
    dependencies=[Depends(require_permission(PermissionAction.CREATE))],
)
def submit_memo(
    memo_id: int,
    payload: MemoSubmit,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
    background_tasks: BackgroundTasks = None,
):
    return MemoService(session).submit_memo(memo_id, payload, current_user, background_tasks)


@router.get(
    "/{memo_id}/download-final-draft",
    summary="Download final approved memo with embedded signatures",
)
def download_final_draft(
    memo_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    """Download the final approved memo as a PDF with embedded signatures.

    The PDF contains:
    - Complete memo content (subject, body)
    - Maker's signature
    - All approver signatures in workflow order
    - Approval metadata

    Only available when the workflow status is APPROVED.
    """
    pdf_path = MemoService(session).generate_final_draft(memo_id, current_user)
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"memo_{memo_id}_final_draft.pdf",
    )
