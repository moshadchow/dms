"""
workflow/approval_policy.py
──────────────────────────
Pure policy functions for workflow approval logic.

These functions are stateless — they take a Session and domain objects,
and return decisions. No class state, no side effects beyond DB reads.
"""

from typing import List

from sqlmodel import Session, select

from correspondence.models import Correspondence, CorrespondenceAttachment
from documents.models import Document
from memos.models import Memo, MemoAttachment
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
                WorkflowStep.is_active == True,
            )
        ).first()
        if not step:
            continue
        if user.id in resolve_eligible_user_ids(session, step, instance.document):
            return True

    return False


def is_eligible_approver_reader(
    session: Session,
    document_id: int,
    user: User,
) -> bool:
    """Read-grant for ``documents/`` read paths (detail, view, download).

    Extends :func:`is_eligible_current_approver` to documents that are
    *attachments* of a memo or correspondence: the in-flight workflow lives on
    the container's backing document, not on the attached document, so the
    direct check alone would miss it (e.g. a memo attachment the current-step
    approver is expected to read). Returns True when the user is an eligible
    approver at the current step of an in-flight instance on either:

    1. the document itself, or
    2. a memo whose ``document_id`` references it via ``memo_attachments``, or
    3. a correspondence with it in ``correspondence_attachments``.
    """
    if is_eligible_current_approver(session, document_id, user):
        return True

    memo_ids = session.exec(
        select(MemoAttachment.memo_id).where(MemoAttachment.document_id == document_id)
    ).all()
    for memo_id in memo_ids:
        memo = session.get(Memo, memo_id)
        if memo and is_eligible_current_approver(session, memo.document_id, user):
            return True

    corr_ids = session.exec(
        select(CorrespondenceAttachment.correspondence_id).where(
            CorrespondenceAttachment.document_id == document_id
        )
    ).all()
    for corr_id in corr_ids:
        corr = session.get(Correspondence, corr_id)
        if corr and corr.document_id and is_eligible_current_approver(
            session, corr.document_id, user
        ):
            return True

    return False
