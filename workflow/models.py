from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from documents.models import Document
    from users.models import User, Role


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class ApprovalMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING_APPROVAL = "pending_approval"
    RETURNED = "returned"
    REJECTED = "rejected"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ──────────────────────────────────────────────
# Link / Association Tables
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
# Workflow Definition
# ──────────────────────────────────────────────

class WorkflowDefinitionBase(SQLModel):
    name: str = Field(max_length=255, index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    is_active: bool = Field(default=True, index=True)


class WorkflowDefinition(WorkflowDefinitionBase, table=True):
    __tablename__ = "workflow_definitions"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_by: int = Field(foreign_key="users.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    created_by_user: "User" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowDefinition.created_by]"}
    )
    steps: List["WorkflowStep"] = Relationship(
        back_populates="workflow_definition",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )


# ──────────────────────────────────────────────
# Workflow Step
# ──────────────────────────────────────────────

class WorkflowStepBase(SQLModel):
    step_order: int = Field(nullable=False)
    step_name: str = Field(max_length=255)
    approval_mode: ApprovalMode = Field(default=ApprovalMode.SEQUENTIAL)
    is_active: bool = Field(default=True)


class WorkflowStep(WorkflowStepBase, table=True):
    __tablename__ = "workflow_steps"

    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_definition_id: int = Field(foreign_key="workflow_definitions.id", index=True, nullable=False)

    workflow_definition: WorkflowDefinition = Relationship(
        back_populates="steps",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    approvers: List["WorkflowStepApprover"] = Relationship(
        back_populates="workflow_step",
        sa_relationship_kwargs={"lazy": "selectin", "cascade": "all, delete-orphan"},
    )


# ──────────────────────────────────────────────
# Workflow Step Approver
# ──────────────────────────────────────────────

class WorkflowStepApproverBase(SQLModel):
    priority: int = Field(default=0, nullable=False)
    is_active: bool = Field(default=True)


class WorkflowStepApprover(WorkflowStepApproverBase, table=True):
    __tablename__ = "workflow_step_approvers"

    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_step_id: int = Field(foreign_key="workflow_steps.id", index=True, nullable=False)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    role_id: Optional[int] = Field(default=None, foreign_key="roles.id")

    workflow_step: WorkflowStep = Relationship(
        back_populates="approvers",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowStepApprover.user_id]"}
    )
    role: Optional["Role"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowStepApprover.role_id]"}
    )


# ──────────────────────────────────────────────
# Approval Action Enum
# ──────────────────────────────────────────────

class ApprovalAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    RETURN = "return"
    CLARIFY = "clarify"
    FORWARD = "forward"


class SignatureType(str, Enum):
    E_SIGNATURE = "e_signature"
    WET_SIGNATURE = "wet_signature"


# ──────────────────────────────────────────────
# Workflow Instance
# ──────────────────────────────────────────────

class WorkflowInstanceBase(SQLModel):
    document_id: int = Field(foreign_key="documents.id", index=True)
    workflow_definition_id: int = Field(foreign_key="workflow_definitions.id", index=True)
    current_step_order: int = Field(default=1, nullable=False)
    status: WorkflowStatus = Field(default=WorkflowStatus.SUBMITTED, index=True)


class WorkflowInstance(WorkflowInstanceBase, table=True):
    __tablename__ = "workflow_instances"

    id: Optional[int] = Field(default=None, primary_key=True)
    submitted_by: int = Field(foreign_key="users.id", nullable=False)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    document: "Document" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowInstance.document_id]"}
    )
    workflow_definition: WorkflowDefinition = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowInstance.workflow_definition_id]"}
    )
    submitted_by_user: "User" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowInstance.submitted_by]"}
    )
    actions: List["WorkflowAction"] = Relationship(
        back_populates="workflow_instance",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    history: List["WorkflowHistory"] = Relationship(
        back_populates="workflow_instance",
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# ──────────────────────────────────────────────
# Workflow Action
# ──────────────────────────────────────────────

class WorkflowActionBase(SQLModel):
    workflow_step_id: int = Field(foreign_key="workflow_steps.id", index=True, nullable=False)
    acted_by: int = Field(foreign_key="users.id", nullable=False)
    action: ApprovalAction = Field(nullable=False)
    remarks: Optional[str] = Field(default=None, max_length=2000)
    signature_id: Optional[int] = Field(default=None, foreign_key="signatures.id")


class WorkflowAction(WorkflowActionBase, table=True):
    __tablename__ = "workflow_actions"

    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_instance_id: int = Field(foreign_key="workflow_instances.id", index=True, nullable=False)
    acted_at: datetime = Field(default_factory=datetime.utcnow)

    workflow_instance: WorkflowInstance = Relationship(
        back_populates="actions",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    acted_by_user: "User" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowAction.acted_by]"}
    )
    workflow_step: WorkflowStep = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowAction.workflow_step_id]"}
    )
    signature: Optional["Signature"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowAction.signature_id]"}
    )


# ──────────────────────────────────────────────
# Workflow History
# ──────────────────────────────────────────────

class WorkflowHistoryBase(SQLModel):
    workflow_instance_id: int = Field(foreign_key="workflow_instances.id", index=True, nullable=False)
    event_type: str = Field(max_length=50, nullable=False)
    actor_id: int = Field(foreign_key="users.id", nullable=False)
    designation_snapshot: Optional[str] = Field(default=None, max_length=100)
    remarks: Optional[str] = Field(default=None, max_length=2000)
    status_snapshot: WorkflowStatus = Field(nullable=False)


class WorkflowHistory(WorkflowHistoryBase, table=True):
    __tablename__ = "workflow_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)

    workflow_instance: WorkflowInstance = Relationship(
        back_populates="history",
        sa_relationship_kwargs={"lazy": "selectin"},
    )
    actor: "User" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[WorkflowHistory.actor_id]"}
    )


# ──────────────────────────────────────────────
# Signature
# ──────────────────────────────────────────────

class SignatureBase(SQLModel):
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    file_name: str = Field(max_length=255, nullable=False)
    file_path: str = Field(max_length=512, nullable=False)
    mime_type: str = Field(max_length=127, nullable=False)
    file_size: int = Field(nullable=False, ge=0)
    sig_type: SignatureType = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)


class Signature(SignatureBase, table=True):
    __tablename__ = "signatures"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user: "User" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Signature.user_id]"}
    )


# ──────────────────────────────────────────────
# Pydantic Read Schemas
# ──────────────────────────────────────────────

class WorkflowStepApproverRead(SQLModel):
    id: int
    workflow_step_id: int
    user_id: Optional[int] = None
    role_id: Optional[int] = None
    priority: int
    is_active: bool
    user_name: Optional[str] = None
    role_name: Optional[str] = None
    model_config = {"from_attributes": True}


class WorkflowStepRead(SQLModel):
    id: int
    workflow_definition_id: int
    step_order: int
    step_name: str
    approval_mode: ApprovalMode
    is_active: bool
    approvers: List[WorkflowStepApproverRead] = []
    model_config = {"from_attributes": True}


class WorkflowDefinitionRead(SQLModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WorkflowDefinitionDetailRead(WorkflowDefinitionRead):
    steps: List[WorkflowStepRead] = []


class WorkflowDefinitionListResponse(SQLModel):
    total: int
    page: int
    limit: int
    items: List[WorkflowDefinitionRead]


# ──────────────────────────────────────────────
# Workflow Instance Read Schemas
# ──────────────────────────────────────────────

class WorkflowActionRead(SQLModel):
    id: int
    workflow_instance_id: int
    workflow_step_id: int
    step_name: Optional[str] = None
    acted_by: int
    acted_by_name: Optional[str] = None
    action: ApprovalAction
    remarks: Optional[str] = None
    signature_id: Optional[int] = None
    acted_at: datetime
    model_config = {"from_attributes": True}


class WorkflowHistoryRead(SQLModel):
    id: int
    workflow_instance_id: int
    event_type: str
    actor_id: int
    actor_name: Optional[str] = None
    designation_snapshot: Optional[str] = None
    remarks: Optional[str] = None
    status_snapshot: WorkflowStatus
    occurred_at: datetime
    model_config = {"from_attributes": True}


class WorkflowInstanceRead(SQLModel):
    id: int
    document_id: int
    document_title: Optional[str] = None
    workflow_definition_id: int
    workflow_name: Optional[str] = None
    current_step_order: int
    current_step_name: Optional[str] = None
    status: WorkflowStatus
    submitted_by: int
    submitted_by_name: Optional[str] = None
    submitted_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WorkflowInstanceDetailRead(WorkflowInstanceRead):
    actions: List[WorkflowActionRead] = []
    history: List[WorkflowHistoryRead] = []


class WorkflowInstanceListResponse(SQLModel):
    total: int
    page: int
    limit: int
    items: List[WorkflowInstanceRead]


class SignatureRead(SQLModel):
    id: int
    user_id: int
    file_name: str
    file_path: str
    mime_type: str
    file_size: int
    sig_type: SignatureType
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
