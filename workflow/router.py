from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from core.database import get_session
from core.dependencies import AdminUser, CurrentUser, require_permission
from users.models import PermissionAction
from workflow.models import (
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
    WorkflowDefinitionService,
    WorkflowInstanceService,
)

router = APIRouter()
instance_router = APIRouter()


# ══════════════════════════════════════════════
# Workflow Definition Endpoints
# ══════════════════════════════════════════════


@router.get(
    "",
    response_model=WorkflowDefinitionListResponse,
    summary="List workflow definitions",
)
def list_workflow_definitions(
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    is_active:  Optional[bool] = Query(None, description="Filter by active status"),
    skip:       int            = Query(0, ge=0),
    limit:      int            = Query(50, ge=1, le=200),
    _:          CurrentUser    = None,
    session:    Session        = Depends(get_session),
):
    return WorkflowDefinitionService(session).list_definitions(
        skip=skip, limit=limit, category_id=category_id, is_active=is_active,
    )


@router.post(
    "",
    response_model=WorkflowDefinitionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create workflow definition (Admin only)",
)
def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    _:       AdminUser = None,
    session: Session   = Depends(get_session),
):
    return WorkflowDefinitionService(session).create_definition(payload, current_user=_)


@router.get(
    "/{definition_id}",
    response_model=WorkflowDefinitionDetailRead,
    summary="Get workflow definition detail",
)
def get_workflow_definition(
    definition_id: int,
    _:             CurrentUser = None,
    session:       Session     = Depends(get_session),
):
    return WorkflowDefinitionService(session).get_definition(definition_id)


@router.put(
    "/{definition_id}",
    response_model=WorkflowDefinitionRead,
    summary="Update workflow definition (Admin only)",
)
def update_workflow_definition(
    definition_id: int,
    payload:       WorkflowDefinitionUpdate,
    _:             AdminUser = None,
    session:       Session   = Depends(get_session),
):
    return WorkflowDefinitionService(session).update_definition(definition_id, payload)


@router.delete(
    "/{definition_id}",
    response_model=WorkflowDefinitionRead,
    status_code=status.HTTP_200_OK,
    summary="Deactivate workflow definition (Admin only)",
)
def deactivate_workflow_definition(
    definition_id: int,
    _:             AdminUser = None,
    session:       Session   = Depends(get_session),
):
    return WorkflowDefinitionService(session).deactivate_definition(definition_id)


@router.patch(
    "/{definition_id}/activate",
    response_model=WorkflowDefinitionRead,
    summary="Activate workflow definition (Admin only)",
)
def activate_workflow_definition(
    definition_id: int,
    _:             AdminUser = None,
    session:       Session   = Depends(get_session),
):
    return WorkflowDefinitionService(session).activate_definition(definition_id)


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
):
    return WorkflowInstanceService(session).submit_instance(payload, current_user)


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
)
def act_on_workflow_instance(
    instance_id:  int,
    payload:      WorkflowActionCreate,
    current_user: CurrentUser = None,
    session:      Session     = Depends(get_session),
):
    return ApprovalActionService(session).act_on_instance(instance_id, payload, current_user)
