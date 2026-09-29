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
from workflow.models import WorkflowInstance, WorkflowStatus, WorkflowStep

#: Instance statuses that appear in a user's pending-approval list. Used by
#: both ``list_pending`` and :func:`is_eligible_current_approver` so the
#: approver read-grant exists exactly while the instance is actionable.
IN_FLIGHT_STATUSES = (WorkflowStatus.SUBMITTED, WorkflowStatus.PENDING_APPROVAL)


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

    Because eligibility does not filter by User Level, modules grant eligible
    current-step approvers read access to the in-flight document in exchange
    (see correspondence ``_check_view_access(approver_view=...)`` and memos
    ``_is_eligible_approver``).
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


def is_eligible_current_approver(
    session: Session,
    document_id: int,
    user: User,
) -> bool:
    """Return True if ``user`` is an eligible approver at the current step
    of an in-flight workflow instance attached to ``document_id``.

    This is the read-grant counterpart of :func:`resolve_eligible_user_ids`:
    modules use it to admit approvers who cannot see the document through
    User Level links, so they can read what they are expected to act on.
    The grant expires once no in-flight instance lists the user — mutations
    keep the strict User Level guard.
    """
    instances = session.exec(
        select(WorkflowInstance).where(
            WorkflowInstance.document_id == document_id,
            WorkflowInstance.status.in_(IN_FLIGHT_STATUSES),
        )
    ).all()

    for instance in instances:
        step = session.exec(
            select(WorkflowStep).where(
                WorkflowStep.workflow_definition_id == instance.workflow_definition_id,
                WorkflowStep.step_order == instance.current_step_order,
            )
        ).first()
        if not step:
            continue
        if user.id in resolve_eligible_user_ids(session, step, instance.document):
            return True

    return False
