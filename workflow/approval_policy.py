"""
workflow/approval_policy.py
──────────────────────────
Pure policy functions for workflow approval logic.

These functions are stateless — they take a Session and domain objects,
and return decisions. No class state, no side effects beyond DB reads.
"""

from typing import List

from sqlmodel import Session, select

from documents.models import Document, DocumentUserLevelLink
from users.models import User, UserRoleLink
from workflow.models import WorkflowStep


def resolve_eligible_user_ids(
    session: Session,
    step: WorkflowStep,
    document: Document,
) -> List[int]:
    """Return user IDs eligible to act at this step, filtered by user level visibility.

    Resolution logic:
    1. Collect users from step.approvers (direct user_id or role expansion).
    2. Fetch DocumentUserLevelLink for the document to get permitted levels.
    3. Filter: inactive users excluded, admins bypass level check, others must match.

    This is the single source of truth for approver eligibility.
    Called by WorkflowInstanceService, ApprovalActionService, and MemoService.
    """
    eligible_ids: set[int] = set()

    for approver in step.approvers:
        if approver.user_id is not None:
            eligible_ids.add(approver.user_id)
        elif approver.role_id is not None:
            role_links = session.exec(
                select(UserRoleLink).where(UserRoleLink.role_id == approver.role_id)
            ).all()
            for link in role_links:
                eligible_ids.add(link.user_id)

    if not eligible_ids:
        return []

    # Filter by user level visibility (admin bypasses)
    user_level_links = session.exec(
        select(DocumentUserLevelLink).where(
            DocumentUserLevelLink.document_id == document.id,
        )
    ).all()
    permitted_level_ids = {link.user_level_id for link in user_level_links}

    # If no level links, document is only visible to admins
    if not permitted_level_ids:
        return []

    result = []
    for uid in eligible_ids:
        user = session.get(User, uid)
        if not user or not user.is_active:
            continue
        if user.is_admin():
            result.append(uid)
            continue
        if user.user_level_id in permitted_level_ids:
            result.append(uid)

    return result
