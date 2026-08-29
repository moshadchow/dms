"""
workflow/approval_policy.py
──────────────────────────
Pure policy functions for workflow approval logic.

These functions are stateless — they take a Session and domain objects,
and return decisions. No class state, no side effects beyond DB reads.
"""

from typing import List

from sqlmodel import Session, select

from documents.models import Document
from users.models import User, UserRoleLink
from workflow.models import WorkflowStep


def resolve_eligible_user_ids(
    session: Session,
    step: WorkflowStep,
    document: Document,
) -> List[int]:
    """Return user IDs eligible to act at this step.

    Resolution logic:
    1. Collect users from step.approvers (direct user_id or role expansion).
    2. Filter out inactive users.

    Approvers are explicitly chosen by the admin for a workflow step.
    The system trusts this selection — user-level visibility is not enforced
    here. The admin configures who approves what; the approval action itself
    is guarded by RBAC permissions separately.
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

    result = []
    for uid in eligible_ids:
        user = session.get(User, uid)
        if not user or not user.is_active:
            continue
        result.append(uid)

    return result
