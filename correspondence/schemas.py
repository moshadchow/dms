from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from correspondence.models import (
    CorrespondenceDirection,
    CorrespondencePriority,
    DispatchMethod,
)


class CorrespondenceCreate(BaseModel):
    """Body for POST /correspondences — create a correspondence draft."""

    direction: CorrespondenceDirection
    subject: str = Field(..., min_length=1, max_length=255)
    body: Optional[str] = Field(None, max_length=50000)
    priority: CorrespondencePriority = CorrespondencePriority.NORMAL
    category_id: Optional[int] = None

    # Sender fields
    sender_name: Optional[str] = Field(None, max_length=255)
    sender_organization: Optional[str] = Field(None, max_length=255)
    sender_email: Optional[str] = Field(None, max_length=255)
    sender_phone: Optional[str] = Field(None, max_length=50)

    # Recipient fields
    recipient_name: Optional[str] = Field(None, max_length=255)
    recipient_organization: Optional[str] = Field(None, max_length=255)
    recipient_email: Optional[str] = Field(None, max_length=255)
    recipient_phone: Optional[str] = Field(None, max_length=50)

    # Dates
    date_received: Optional[datetime] = None

    # Response tracking
    response_required: bool = False
    response_deadline: Optional[datetime] = None
    parent_correspondence_id: Optional[int] = None

    # User levels
    user_level_ids: List[int] = Field(default_factory=list)

    # Inbound: existing uploaded document
    document_id: Optional[int] = None

    # Outbound: author signature
    author_signature_id: Optional[int] = None


class CorrespondenceUpdate(BaseModel):
    """Body for PATCH /correspondences/{id} — update a correspondence."""

    subject: Optional[str] = Field(None, min_length=1, max_length=255)
    body: Optional[str] = Field(None, max_length=50000)
    priority: Optional[CorrespondencePriority] = None
    category_id: Optional[int] = None

    sender_name: Optional[str] = Field(None, max_length=255)
    sender_organization: Optional[str] = Field(None, max_length=255)
    sender_email: Optional[str] = Field(None, max_length=255)
    sender_phone: Optional[str] = Field(None, max_length=50)

    recipient_name: Optional[str] = Field(None, max_length=255)
    recipient_organization: Optional[str] = Field(None, max_length=255)
    recipient_email: Optional[str] = Field(None, max_length=255)
    recipient_phone: Optional[str] = Field(None, max_length=50)

    response_required: Optional[bool] = None
    response_deadline: Optional[datetime] = None

    user_level_ids: Optional[List[int]] = None
    author_signature_id: Optional[int] = None


class CorrespondenceSubmit(BaseModel):
    """Body for POST /correspondences/{id}/submit — submit for workflow approval."""

    workflow_definition_id: int = Field(..., description="FK -> workflow_definitions.id")
    signature_id: Optional[int] = Field(None, description="Author's signature")


class CorrespondenceAssign(BaseModel):
    """Body for POST /correspondences/{id}/assign — assign to a user."""

    to_user_id: int
    remarks: Optional[str] = None


class CorrespondenceDispatch(BaseModel):
    """Body for POST /correspondences/{id}/dispatch — mark as dispatched."""

    dispatch_method: DispatchMethod
    dispatch_reference: Optional[str] = Field(None, max_length=255)
    remarks: Optional[str] = None


class CorrespondenceDeliver(BaseModel):
    """Body for POST /correspondences/{id}/deliver — mark as delivered."""

    delivered_at: Optional[datetime] = None
    remarks: Optional[str] = None


class CorrespondenceAcknowledge(BaseModel):
    """Body for POST /correspondences/{id}/acknowledge — mark as acknowledged."""

    acknowledged_at: Optional[datetime] = None
    remarks: Optional[str] = None
