from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MemoCreate(BaseModel):
    """Body for POST /memos — create a memo draft.

    The memo's backing document is created automatically and placed in
    ``directory_id``. User levels control visibility (as with document uploads).
    """

    directory_id: int = Field(..., description="Target directory for the memo document")
    user_level_ids: List[int] = Field(
        default_factory=list,
        description="User level IDs permitted to view this memo",
    )
    memo_date: Optional[datetime] = Field(None, description="Defaults to now")
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field("", max_length=50000, description="HTML body content from rich-text editor")
    attachment_document_ids: List[int] = Field(
        default_factory=list,
        description="Existing document IDs to attach as supporting evidence",
    )


class MemoUpdate(BaseModel):
    """Body for PATCH /memos/{memo_id} — update a memo.

    All fields optional. Author may update any field; eligible approvers may
    update the draft body/subject/recipients while the memo is in the workflow.
    Submitter may also update content/attachments/signature while the memo is
    in submitted/pending_approval status (before approval).
    """

    memo_date: Optional[datetime] = None
    subject: Optional[str] = Field(None, min_length=1, max_length=255)
    body: Optional[str] = Field(None, max_length=50000)
    user_level_ids: Optional[List[int]] = Field(
        None,
        description="If provided, replaces the full user-level visibility set",
    )
    attachment_document_ids: Optional[List[int]] = Field(
        None,
        description="If provided, replaces the full attachment set",
    )
    signature_id: Optional[int] = Field(
        None,
        description="FK → signatures.id — author's signature (e-signature or wet-signature)",
    )


class MemoSubmit(BaseModel):
    """Body for POST /memos/{memo_id}/submit — route memo through approval."""

    workflow_definition_id: int = Field(..., description="FK → workflow_definitions.id")
    signature_id: Optional[int] = Field(None, description="Author's signature (e-signature or wet-signature)")
