"""
workflow/schemas.py
───────────────────
Pydantic request / response schemas for the Workflow endpoints.

Phase 1: Workflow definition configuration (admin-only create/update).
Phase 2: Workflow instance submission and approval actions.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from workflow.models import ApprovalMode, ApprovalAction, SignatureType


# ══════════════════════════════════════════════
# Create
# ══════════════════════════════════════════════


class WorkflowStepApproverCreate(BaseModel):
    """Single approver entry within a workflow step."""

    user_id: Optional[int] = Field(None, description="User ID (mutually exclusive with role_id)")
    role_id: Optional[int] = Field(None, description="Role ID (mutually exclusive with user_id)")


class WorkflowStepCreate(BaseModel):
    """Single step within a workflow definition."""

    step_order: int = Field(..., ge=1, description="1-based step ordering")
    step_name: str = Field(..., min_length=1, max_length=255, description="Human-readable step name")
    approval_mode: ApprovalMode = Field(
        default=ApprovalMode.SEQUENTIAL,
        description="'sequential' = all approvers must act; 'parallel' = any one suffices",
    )
    approvers: List[WorkflowStepApproverCreate] = Field(
        default_factory=list,
        description="At least one approver required per step",
    )


class WorkflowDefinitionCreate(BaseModel):
    """
    Body for POST /workflows — Admin only.

    Creates a workflow definition with its steps and approvers in a single call.
    """

    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Unique workflow name",
        examples=["Invoice Approval"],
    )
    description: Optional[str] = Field(None, max_length=1000)
    steps: List[WorkflowStepCreate] = Field(
        ...,
        min_length=1,
        description="Ordered list of approval steps (at least one required)",
    )


# ══════════════════════════════════════════════
# Update
# ══════════════════════════════════════════════


class WorkflowDefinitionUpdate(BaseModel):
    """
    Body for PUT /workflows/{id} — Admin only.

    Full replacement of steps and approvers. Omitted optional fields retain
    their current values.
    """

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None
    steps: Optional[List[WorkflowStepCreate]] = Field(
        None,
        description="If provided, replaces all existing steps and approvers",
    )


# ══════════════════════════════════════════════
# Phase 2 — Workflow Instance
# ══════════════════════════════════════════════


class WorkflowInstanceCreate(BaseModel):
    """
    Body for POST /workflow-instances — submit a document for approval.
    """

    document_id: int = Field(..., description="FK → documents.id")
    workflow_definition_id: int = Field(..., description="FK → workflow_definitions.id")


class WorkflowActionCreate(BaseModel):
    """
    Body for POST /workflow-instances/{id}/actions — approve/reject/return/clarify.
    """

    action: ApprovalAction = Field(..., description="Action to perform")
    remarks: Optional[str] = Field(None, max_length=2000, description="Optional remarks")
    signature_id: Optional[int] = Field(None, description="FK → signatures.id (Phase 3)")


# ══════════════════════════════════════════════
# Phase 3 — Signature
# ══════════════════════════════════════════════


class SignatureCreate(BaseModel):
    """
    Metadata for signature upload. The actual file is sent as multipart form data.
    """

    sig_type: SignatureType = Field(
        ...,
        description="Type of signature: 'e_signature' for uploaded image, 'wet_signature' for canvas capture",
    )
