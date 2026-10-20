import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from sqlmodel import Session, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from core.config import settings
from memos.models import MemoDetailRead
from notifications.models import EmailNotification
from users.models import User
from workflow.models import WorkflowDefinitionDetailRead, WorkflowInstanceDetailRead, WorkflowStepRead

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, session: Session):
        self.session = session

    def _send_smtp(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        """Core SMTP send. Returns True on success, False on failure. Never raises exceptions."""
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            logger.warning("SMTP not configured, skipping email send")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = to_email

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            if settings.SMTP_USE_TLS:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.starttls()
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.send_message(msg)

            return True

        except Exception as e:
            logger.exception(f"Failed to send email to {to_email}: {e}")
            return False

    def _is_already_sent(
        self, instance_id: int, step_order: int, recipient_id: int, notif_type: str
    ) -> bool:
        """Idempotency check against email_notifications table."""
        stmt = select(EmailNotification).where(
            EmailNotification.instance_id == instance_id,
            EmailNotification.step_order == step_order,
            EmailNotification.recipient_user_id == recipient_id,
            EmailNotification.notification_type == notif_type,
            EmailNotification.status == "sent",
        )
        existing = self.session.exec(stmt).first()
        return existing is not None

    def _record_send(
        self,
        instance_id: int,
        step_order: int,
        recipient_id: int,
        notif_type: str,
        status: str,
        error: Optional[str] = None,
    ) -> EmailNotification:
        """Write EmailNotification record + AuditService log."""
        notification = EmailNotification(
            instance_id=instance_id,
            step_order=step_order,
            recipient_user_id=recipient_id,
            notification_type=notif_type,
            status=status,
            error_message=error,
        )
        self.session.add(notification)
        self.session.commit()
        self.session.refresh(notification)

        # Log to audit
        try:
            AuditService(self.session).log_event(
                action=(
                    AuditAction.EMAIL_SENT
                    if status == "sent"
                    else AuditAction.EMAIL_FAILED
                ),
                module=AuditModule.WORKFLOW,
                entity_name="email_notification",
                entity_id=str(notification.id),
                description=f"Email {status}: {notif_type} for instance {instance_id}",
                is_success=(status == "sent"),
                failure_reason=error,
            )
        except Exception:
            logger.exception("Failed to log email audit event")

        return notification

    def resolve_recipients(self, step: WorkflowStepRead, document) -> List[User]:
        """Resolve eligible users from workflow step approvers (user-based or role-based)."""
        from workflow.approval_policy import resolve_eligible_user_ids

        # We need to fetch the actual WorkflowStep ORM object for resolve_eligible_user_ids
        # For now, delegate to approval_policy which works with ORM objects
        # This method will be called with the ORM step from the service layer
        pass

    def send_workflow_notification(
        self,
        instance: WorkflowInstanceDetailRead,
        document,
        workflow_def: WorkflowDefinitionDetailRead,
        step: WorkflowStepRead,
        notification_type: str,
        background_tasks,
    ) -> None:
        """Enqueue a notification as a background task."""
        from notifications.tasks import send_notification_task

        background_tasks.add_task(
            send_notification_task,
            notification_type=notification_type,
            instance_id=instance.id,
            document_id=document.id,
            step_order=step.step_order,
        )