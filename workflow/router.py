from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from core.database import get_session
from core.dependencies import AdminUser, CurrentUser, require_permission
from users.models import PermissionAction
from workflow.models import (
    SignatureRead,
    SignatureType,
    WorkflowActionRead,
    WorkflowDefinitionDetailRead,
    WorkflowDefinitionListResponse,
    WorkflowDefinitionRead,
    WorkflowHistoryRead,
    WorkflowInstanceDetailRead,
    WorkflowInstanceListResponse,
    WorkflowInstanceRead,
    WorkflowStepRead,
)
from workflow.schemas import (
    WorkflowActionCreate,
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowInstanceCreate,
)
from workflow.service import (
    ApprovalActionService,
    SignatureService,
    WorkflowDefinitionService,
    WorkflowInstanceService,
)

router = APIRouter()
instance_router = APIRouter()
signature_router = APIRouter()


# ══════════════════════════════════════════════
# Workflow Definition Endpoints
# ══════════════════════════════════════════════


@router.get(
    "",
    response_model=WorkflowDefinitionListResponse,
    summary="List workflow definitions",
)
def list_workflow_definitions(
    is_active:  Optional[bool] = Query(None, description="Filter by active status"),
    company_id: Optional[int]  = Query(None, description="Filter by company (SUPERADMIN only)"),
    skip:       int            = Query(0, ge=0),
    limit:      int            = Query(50, ge=1, le=200),
    current_user: CurrentUser  = None,
    session:    Session        = Depends(get_session),
):
    return WorkflowDefinitionService(session).list_definitions(
        skip=skip, limit=limit, is_active=is_active,
        company_id=company_id, current_user=current_user,
    )


@router.post(
    "",
    response_model=WorkflowDefinitionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create workflow definition (Admin only)",
)
def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    current_user: AdminUser = None,
    session: Session   = Depends(get_session),
):
    return WorkflowDefinitionService(session).create_definition(payload, current_user=current_user)


@router.get(
    "/{definition_id}",
    response_model=WorkflowDefinitionDetailRead,
    summary="Get workflow definition detail",
)
def get_workflow_definition(
    definition_id: int,
    current_user:   CurrentUser = None,
    session:        Session     = Depends(get_session),
):
    return WorkflowDefinitionService(session).get_definition(definition_id, current_user)


@router.put(
    "/{definition_id}",
    response_model=WorkflowDefinitionRead,
    summary="Update workflow definition (Admin only)",
)
def update_workflow_definition(
    definition_id: int,
    payload:       WorkflowDefinitionUpdate,
    current_user:  AdminUser = None,
    session:       Session   = Depends(get_session),
):
    return WorkflowDefinitionService(session).update_definition(definition_id, payload, current_user)


@router.delete(
    "/{definition_id}",
    response_model=WorkflowDefinitionRead,
    status_code=status.HTTP_200_OK,
    summary="Deactivate workflow definition (Admin only)",
)
def deactivate_workflow_definition(
    definition_id: int,
    current_user:  AdminUser = None,
    session:       Session   = Depends(get_session),
):
    return WorkflowDefinitionService(session).deactivate_definition(definition_id, current_user)


@router.patch(
    "/{definition_id}/activate",
    response_model=WorkflowDefinitionRead,
    summary="Activate workflow definition (Admin only)",
)
def activate_workflow_definition(
    definition_id: int,
    current_user:  AdminUser = None,
    session:       Session   = Depends(get_session),
):
    return WorkflowDefinitionService(session).activate_definition(definition_id, current_user)


# ══════════════════════════════════════════════
# Workflow Instance Endpoints
# ══════════════════════════════════════════════


@instance_router.post(
    "",
    response_model=WorkflowInstanceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a document for approval",
    dependencies=[Depends(require_permission(PermissionAction.CREATE))],
)
def submit_workflow_instance(
    payload:      WorkflowInstanceCreate,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
    background_tasks: BackgroundTasks = None,
):
    return WorkflowInstanceService(session).submit_instance(payload, current_user, background_tasks)


@instance_router.get(
    "/pending",
    response_model=WorkflowInstanceListResponse,
    summary="Pending approvals for current user",
)
def list_pending_instances(
    skip:         int         = Query(0, ge=0),
    limit:        int         = Query(50, ge=1, le=200),
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    return WorkflowInstanceService(session).list_pending(
        current_user, skip=skip, limit=limit,
    )


@instance_router.get(
    "/mine",
    response_model=WorkflowInstanceListResponse,
    summary="Instances submitted by current user",
)
def list_my_instances(
    skip:         int         = Query(0, ge=0),
    limit:        int         = Query(50, ge=1, le=200),
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    return WorkflowInstanceService(session).list_my_instances(
        current_user, skip=skip, limit=limit,
    )


@instance_router.get(
    "/by-document/{document_id}",
    response_model=WorkflowInstanceDetailRead,
    summary="Get the latest workflow instance for a document",
)
def get_workflow_instance_by_document(
    document_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return WorkflowInstanceService(session).get_by_document(document_id, current_user)


@instance_router.get(
    "/{instance_id}",
    response_model=WorkflowInstanceDetailRead,
    summary="Get workflow instance detail",
)
def get_workflow_instance(
    instance_id:  int,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    return WorkflowInstanceService(session).get_instance(instance_id)


@instance_router.post(
    "/{instance_id}/actions",
    response_model=WorkflowInstanceRead,
    summary="Act on a workflow instance (approve/reject/return/clarify)",
    dependencies=[Depends(require_permission(PermissionAction.UPDATE))],
)
def act_on_workflow_instance(
    instance_id:  int,
    payload:      WorkflowActionCreate,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
    background_tasks: BackgroundTasks = None,
):
    return ApprovalActionService(session).act_on_instance(instance_id, payload, current_user, background_tasks)


@instance_router.post(
    "/{instance_id}/cancel",
    response_model=WorkflowInstanceRead,
    summary="Cancel a submitted workflow instance (submitter only)",
)
def cancel_workflow_instance(
    instance_id:  int,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    return WorkflowInstanceService(session).cancel_instance(instance_id, current_user)


# ══════════════════════════════════════════════
# Signature Endpoints
# ══════════════════════════════════════════════


@signature_router.post(
    "",
    response_model=SignatureRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a signature image",
)
def upload_signature(
    file:    UploadFile = File(..., description="Signature image (JPEG or PNG)"),
    sig_type: str       = Form(..., description="Signature type: e_signature or wet_signature"),
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    # Convert string to enum
    try:
        sig_type_enum = SignatureType(sig_type)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sig_type '{sig_type}'. Must be 'e_signature' or 'wet_signature'",
        )
    return SignatureService(session).upload_signature(file, current_user, sig_type_enum)


@signature_router.get(
    "",
    response_model=List[SignatureRead],
    summary="List current user's signatures",
)
def list_signatures(
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return SignatureService(session).list_signatures(current_user)


@signature_router.get(
    "/{signature_id}",
    response_model=SignatureRead,
    summary="Get signature metadata",
)
def get_signature(
    signature_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return SignatureService(session).get_signature(signature_id, current_user)


@signature_router.get(
    "/{signature_id}/file",
    summary="Serve signature file",
)
def get_signature_file(
    signature_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    svc = SignatureService(session)
    file_path = svc.get_signature_file(signature_id, current_user)
    sig = svc.get_signature(signature_id, current_user)
    return FileResponse(
        path=str(file_path),
        media_type=sig.mime_type,
        filename=sig.file_name,
    )


@signature_router.delete(
    "/{signature_id}",
    response_model=SignatureRead,
    summary="Soft-delete a signature",
)
def delete_signature(
    signature_id: int,
    current_user: CurrentUser = None,
    session: Session = Depends(get_session),
):
    return SignatureService(session).soft_delete_signature(signature_id, current_user)


# ══════════════════════════════════════════════
# Admin Signature Endpoints
# ══════════════════════════════════════════════


@signature_router.get(
    "/admin/{target_user_id}",
    response_model=List[SignatureRead],
    summary="List signatures for a specific user (admin only)",
)
def admin_list_user_signatures(
    target_user_id: int,
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    return SignatureService(session).list_user_signatures(target_user_id, current_user)


@signature_router.post(
    "/admin/{target_user_id}",
    response_model=SignatureRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload signature for a user (admin only)",
)
def admin_upload_signature(
    target_user_id: int,
    file: UploadFile = File(..., description="Signature image (JPEG or PNG)"),
    sig_type: str = Form(..., description="Signature type: e_signature or wet_signature"),
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    try:
        sig_type_enum = SignatureType(sig_type)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sig_type '{sig_type}'. Must be 'e_signature' or 'wet_signature'",
        )
    return SignatureService(session).admin_upload_for_user(
        target_user_id, file, current_user, sig_type_enum
    )


@signature_router.delete(
    "/admin/{target_user_id}/{signature_id}",
    response_model=SignatureRead,
    summary="Delete a user's signature (admin only)",
)
def admin_delete_signature(
    target_user_id: int,
    signature_id: int,
    current_user: AdminUser = None,
    session: Session = Depends(get_session),
):
    return SignatureService(session).admin_delete_signature(
        target_user_id, signature_id, current_user
    )
