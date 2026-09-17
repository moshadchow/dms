from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from categories.models import Category
    from company_profile.models import Company
    from documents.models import Document
    from users.models import User
    from workflow.models import Signature, WorkflowInstance


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class CorrespondenceDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class CorrespondencePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class CorrespondenceStatus(str, Enum):
    # Inbound lifecycle
    RECEIVED = "received"
    REGISTERED = "registered"
    ASSIGNED = "assigned"
    PROCESSING = "processing"
    # Shared
    DRAFT = "draft"
    SUBMITTED = "submitted"
    PENDING_APPROVAL = "pending_approval"
    RETURNED = "returned"
    REJECTED = "rejected"
    APPROVED = "approved"
    # Dispatch
    READY_FOR_DISPATCH = "ready_for_dispatch"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    # Terminal
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class DispatchMethod(str, Enum):
    EMAIL = "email"
    COURIER = "courier"
    POST = "post"
    HAND_DELIVERY = "hand_delivery"
    PORTAL = "portal"
    OTHER = "other"


class AttachmentType(str, Enum):
    ORIGINAL = "original"
    SUPPORTING = "supporting"
    WORKING = "working"


# ──────────────────────────────────────────────
# Database Tables
# ──────────────────────────────────────────────

class Correspondence(SQLModel, table=True):
    __tablename__ = "correspondences"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: Optional[int] = Field(default=None, foreign_key="documents.id", index=True, nullable=True, unique=True)
    company_id: int = Field(foreign_key="companies.id", nullable=False, index=True)
    created_by: int = Field(foreign_key="users.id", nullable=False)
    reference_number: str = Field(max_length=50, nullable=False, unique=True, index=True)

    direction: CorrespondenceDirection = Field(nullable=False, index=True)
    status: CorrespondenceStatus = Field(default=CorrespondenceStatus.DRAFT, nullable=False, index=True)
    subject: str = Field(max_length=255, index=True)
    body: Optional[str] = Field(default=None, max_length=50000)
    priority: CorrespondencePriority = Field(default=CorrespondencePriority.NORMAL, nullable=False, index=True)
    category_id: Optional[int] = Field(default=None, foreign_key="categories.id", index=True)

    # Sender
    sender_name: Optional[str] = Field(default=None, max_length=255)
    sender_organization: Optional[str] = Field(default=None, max_length=255)
    sender_email: Optional[str] = Field(default=None, max_length=255)
    sender_phone: Optional[str] = Field(default=None, max_length=50)

    # Recipient
    recipient_name: Optional[str] = Field(default=None, max_length=255)
    recipient_organization: Optional[str] = Field(default=None, max_length=255)
    recipient_email: Optional[str] = Field(default=None, max_length=255)
    recipient_phone: Optional[str] = Field(default=None, max_length=50)

    # Dates
    date_sent: Optional[datetime] = Field(default=None, index=True)
    date_received: Optional[datetime] = Field(default=None, index=True)

    # Response tracking
    response_required: bool = Field(default=False, nullable=False)
    response_deadline: Optional[datetime] = Field(default=None, index=True)
    response_received: bool = Field(default=False, nullable=False)
    responded_at: Optional[datetime] = Field(default=None)

    # Relationships
    parent_correspondence_id: Optional[int] = Field(default=None, foreign_key="correspondences.id", index=True)
    author_signature_id: Optional[int] = Field(default=None, foreign_key="signatures.id")
    workflow_instance_id: Optional[int] = Field(default=None, foreign_key="workflow_instances.id", index=True)

    # Dispatch
    dispatch_method: Optional[DispatchMethod] = Field(default=None)
    dispatch_reference: Optional[str] = Field(default=None, max_length=255)
    dispatched_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    acknowledged_at: Optional[datetime] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Relationships
    document: "Document" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Correspondence.document_id]"}
    )
    company: "Company" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    created_by_user: "User" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Correspondence.created_by]"}
    )
    category: Optional["Category"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin"}
    )
    parent: Optional["Correspondence"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Correspondence.parent_correspondence_id]"}
    )
    author_signature: Optional["Signature"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Correspondence.author_signature_id]"}
    )
    workflow_instance: Optional["WorkflowInstance"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[Correspondence.workflow_instance_id]"}
    )
    attachment_links: List["CorrespondenceAttachment"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[CorrespondenceAttachment.correspondence_id]",
                               "viewonly": True}
    )


class CorrespondenceMovement(SQLModel, table=True):
    __tablename__ = "correspondence_movements"

    id: Optional[int] = Field(default=None, primary_key=True)
    correspondence_id: int = Field(foreign_key="correspondences.id", nullable=False, index=True)
    from_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    to_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    from_department: Optional[str] = Field(default=None, max_length=255)
    to_department: Optional[str] = Field(default=None, max_length=255)
    action: str = Field(max_length=50, nullable=False)
    remarks: Optional[str] = Field(default=None)
    created_by: int = Field(foreign_key="users.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    correspondence: "Correspondence" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[CorrespondenceMovement.correspondence_id]"}
    )
    from_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[CorrespondenceMovement.from_user_id]"}
    )
    to_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[CorrespondenceMovement.to_user_id]"}
    )
    actor: "User" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[CorrespondenceMovement.created_by]"}
    )


class CorrespondenceSequence(SQLModel, table=True):
    __tablename__ = "correspondence_sequences"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="companies.id", nullable=False, index=True)
    year: int = Field(nullable=False)
    last_value: int = Field(default=0, nullable=False)

    company: "Company" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin"}
    )


class CorrespondenceAttachment(SQLModel, table=True):
    __tablename__ = "correspondence_attachments"

    id: Optional[int] = Field(default=None, primary_key=True)
    correspondence_id: int = Field(foreign_key="correspondences.id", nullable=False, index=True)
    document_id: int = Field(foreign_key="documents.id", nullable=False, index=True)
    attachment_type: AttachmentType = Field(default=AttachmentType.SUPPORTING, nullable=False)
    created_by: int = Field(foreign_key="users.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    correspondence: "Correspondence" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[CorrespondenceAttachment.correspondence_id]"}
    )
    document: "Document" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[CorrespondenceAttachment.document_id]"}
    )
    creator: "User" = Relationship(
        sa_relationship_kwargs={"lazy": "selectin", "foreign_keys": "[CorrespondenceAttachment.created_by]"}
    )


# ──────────────────────────────────────────────
# Pydantic Read Schemas
# ──────────────────────────────────────────────

class CorrespondenceRead(SQLModel):
    id: int
    document_id: Optional[int] = None
    company_id: int
    created_by: int
    reference_number: str
    direction: CorrespondenceDirection
    status: CorrespondenceStatus
    subject: str
    body: Optional[str] = None
    priority: CorrespondencePriority
    category_id: Optional[int] = None
    sender_name: Optional[str] = None
    sender_organization: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_organization: Optional[str] = None
    date_sent: Optional[datetime] = None
    date_received: Optional[datetime] = None
    response_required: bool = False
    response_deadline: Optional[datetime] = None
    response_received: bool = False
    responded_at: Optional[datetime] = None
    parent_correspondence_id: Optional[int] = None
    author_signature_id: Optional[int] = None
    workflow_instance_id: Optional[int] = None
    dispatch_method: Optional[DispatchMethod] = None
    dispatch_reference: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    created_by_name: Optional[str] = None
    category_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class CorrespondenceMovementRead(SQLModel):
    id: int
    correspondence_id: int
    from_user_id: Optional[int] = None
    from_user_name: Optional[str] = None
    to_user_id: Optional[int] = None
    to_user_name: Optional[str] = None
    from_department: Optional[str] = None
    to_department: Optional[str] = None
    action: str
    remarks: Optional[str] = None
    created_by: int
    created_by_name: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class CorrespondenceAttachmentRead(SQLModel):
    id: int
    correspondence_id: int
    document_id: int
    attachment_type: AttachmentType
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    created_by: int
    created_by_name: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class CorrespondenceDetailRead(CorrespondenceRead):
    sender_email: Optional[str] = None
    sender_phone: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    document_title: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    movements: List[CorrespondenceMovementRead] = []
    attachments: List[CorrespondenceAttachmentRead] = []
    user_level_ids: List[int] = []
    parent_reference: Optional[str] = None
    workflow_status: Optional[str] = None


class CorrespondenceListResponse(SQLModel):
    total: int
    items: List[CorrespondenceRead]
