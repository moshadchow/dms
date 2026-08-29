import logging
from typing import Optional

from sqlmodel import Session, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from core.config import settings
from core.database import engine
from memos.models import MemoDetailRead
from memos.service import MemoService
from notifications.models import EmailNotification
from notifications.service import EmailService
from notifications.templates import (
    build_submit_email,
    build_advance_email,
    build_action_email,
)
from workflow.models import (
    WorkflowStepRead,
)
from users.models import User
from workflow.service import WorkflowInstanceService

logger = logging.getLogger(__name__)


def send_notification_task(
    notification_type: str,
    instance_id: int,
    document_id: int,
    step_order: Optional[int] = None,
) -> None:
    """
    Runs in background thread. Creates its own DB session.
    Resolves recipients, checks idempotency, sends emails, logs results.
    """
    with Session(engine) as session:
        try:
            # 1. Fetch instance, document, workflow definition
            from workflow.models import WorkflowInstance, WorkflowAction, WorkflowDefinition, WorkflowStep
            from documents.models import Document
            from memos.models import Memo

            instance_orm = session.get(WorkflowInstance, instance_id)
            if not instance_orm:
                logger.warning(f"WorkflowInstance {instance_id} not found (ORM)")
                return

            document_orm = session.get(Document, document_id)
            if not document_orm:
                logger.warning(f"Document {document_id} not found")
                return

            workflow_def_orm = session.get(WorkflowDefinition, instance_orm.workflow_definition_id)
            if not workflow_def_orm:
                logger.warning(f"WorkflowDefinition {instance_orm.workflow_definition_id} not found")
                return

            # Get memo if this is a memo workflow
            memo_orm = None
            memo_detail = None
            if document_orm:
                memo_orm = session.exec(
                    select(Memo).where(Memo.document_id == document_id)
                ).first()
                if memo_orm:
                    memo_detail = MemoService(session)._to_detail(memo_orm)

            # Get the current step
            step_orm = session.exec(
                select(WorkflowStep).where(
                    WorkflowStep.workflow_definition_id == workflow_def_orm.id,
                    WorkflowStep.step_order == (step_order or instance_orm.current_step_order),
                )
            ).first()

            if not step_orm:
                logger.warning(f"WorkflowStep not found for instance {instance_id}, step {step_order or instance_orm.current_step_order}")
                return

            # Convert to detail schemas for templates
            from workflow.service import WorkflowInstanceService, WorkflowDefinitionService

            instance_detail = WorkflowInstanceService(session)._to_instance_detail(instance_orm)
            workflow_def_detail = WorkflowDefinitionService(session).get_definition(workflow_def_orm.id)

            # Build step detail
            step_detail = WorkflowStepRead(
                id=step_orm.id,
                workflow_definition_id=step_orm.workflow_definition_id,
                step_order=step_orm.step_order,
                step_name=step_orm.step_name,
                approval_mode=step_orm.approval_mode,
                is_active=step_orm.is_active,
                approvers=[
                    type('obj', (object,), {
                        'id': a.id,
                        'workflow_step_id': a.workflow_step_id,
                        'user_id': a.user_id,
                        'role_id': a.role_id,
                        'is_active': a.is_active,
                        'user_name': a.user.full_name if a.user else None,
                        'role_name': a.role.name.value if a.role else None,
                    })()
                    for a in step_orm.approvers if a.is_active
                ],
            )

            # Resolve recipients based on notification type
            recipients = []
            if notification_type in ("submit", "advance"):
                # Notify approvers for the active/next step
                from workflow.approval_policy import resolve_eligible_user_ids
                eligible_user_ids = resolve_eligible_user_ids(session, step_orm, document_orm)
                if eligible_user_ids:
                    recipients = session.exec(
                        select(User).where(User.id.in_(eligible_user_ids))
                    ).all()
            elif notification_type in ("action", "approved"):
                # Notify the submitter
                submitter = session.get(User, instance_orm.submitted_by)
                if submitter:
                    recipients = [submitter]

            if not recipients:
                logger.info(f"No recipients found for {notification_type} notification on instance {instance_id}")
                return

            # Initialize email service
            email_service = EmailService(session)

            # Send to each recipient
            for recipient in recipients:
                # Idempotency check
                check_step_order = step_order or instance_orm.current_step_order
                if email_service._is_already_sent(instance_id, check_step_order, recipient.id, notification_type):
                    logger.debug(f"Email already sent to user {recipient.id} for instance {instance_id}, type {notification_type}")
                    continue

                # Build email content
                subject = html_body = text_body = None
                if notification_type == "submit" and memo_detail:
                    subject, html_body, text_body = build_submit_email(
                        memo_detail, workflow_def_detail, step_detail, instance_detail
                    )
                elif notification_type == "advance" and memo_detail:
                    subject, html_body, text_body = build_advance_email(
                        memo_detail, workflow_def_detail, step_detail, instance_detail
                    )
                elif notification_type in ("action", "approved") and memo_detail:
                    # Get actor name from the latest action
                    latest_action = session.exec(
                        select(WorkflowAction)
                        .where(WorkflowAction.workflow_instance_id == instance_id)
                        .order_by(WorkflowAction.acted_at.desc())
                    ).first()
                    actor_name = latest_action.acted_by_user.full_name if latest_action and latest_action.acted_by_user else "Unknown"
                    remarks = latest_action.remarks if latest_action else None
                    action_value = latest_action.action.value if latest_action else notification_type
                    subject, html_body, text_body = build_action_email(
                        memo_detail, instance_detail, action_value, actor_name, remarks
                    )

                if subject and html_body and text_body:
                    review_url = f"{settings.FRONTEND_URL}/approvals/pending"

                    html_body = html_body.replace("PLACEHOLDER", review_url)
                    text_body = text_body.replace("PLACEHOLDER", review_url)

                    success = email_service._send_smtp(
                        to_email=recipient.email,
                        subject=subject,
                        html_body=html_body,
                        text_body=text_body,
                    )

                    email_service._record_send(
                        instance_id=instance_id,
                        step_order=check_step_order,
                        recipient_id=recipient.id,
                        notif_type=notification_type,
                        status="sent" if success else "failed",
                        error=None if success else "SMTP send failed",
                    )

                    logger.info(f"Email {notification_type} {'sent' if success else 'failed'} to {recipient.email} for instance {instance_id}")

        except Exception as e:
            logger.exception(f"Error in send_notification_task for instance {instance_id}: {e}")