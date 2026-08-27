Finalized Implementation Plan: Email Notification System
Architecture Decision
Email delivery: Raw smtplib (stdlib) via FastAPI BackgroundTasks (runs in a thread pool). No new dependencies. The app is synchronous, SMTP sends are fast (~100-500ms), and BackgroundTasks handles the threading. Retry logic is handled via the email_notifications tracking table — a future periodic task can re-attempt failed sends.
Notification flow:
Workflow event (submit/approve/reject/return)
  → WorkflowService calls BackgroundTasks.add_task()
    → Background task creates its own DB session
      → EmailService resolves recipients from workflow config
        → Idempotency check against email_notifications table
          → Build HTML email from template
            → Send via smtplib
              → Log result to AuditService + email_notifications table
Step 1: SMTP Configuration
Files: core/config.py, .env.example
Add to Settings class in core/config.py:
# -- SMTP / Email --
SMTP_HOST:      str  = ""
SMTP_PORT:      int  = 587
SMTP_USERNAME:  str  = ""
SMTP_PASSWORD:  str  = ""
SMTP_FROM_EMAIL: str = ""
SMTP_USE_TLS:   bool = True
SMTP_FROM_NAME: str  = "DMS"
Add corresponding section to .env.example with comments.
Step 2: Email Notification Table + Migration
New file: notifications/__init__.py (empty), notifications/models.py
class EmailNotification(SQLModel, table=True):
    __tablename__ = "email_notifications"

    id:                Optional[int]  # PK
    instance_id:       int            # FK → workflow_instances.id
    step_order:        int
    recipient_user_id: int            # FK → users.id
    notification_type: str            # "submit" | "advance" | "action" | "approved"
    status:            str            # "pending" | "sent" | "failed"
    error_message:     Optional[str]
    created_at:        datetime
    sent_at:           Optional[datetime]
Migration: alembic revision --autogenerate -m "add email_notifications table"
- Down revision: f2a3b4c5d6e7 (current head)
- Creates email_notifications table with indexes on (instance_id, step_order, recipient_user_id, notification_type) for idempotency lookups
Also update: migrations/env.py — add import notifications.models alongside existing module imports (required for --autogenerate to detect the new table).
Step 3: Email Templates
New file: notifications/templates.py
Three HTML template builder functions, each returning (subject, html_body, text_body):
Function	Trigger	Recipients
build_submit_email(memo, workflow_def, step, instance, review_url)	Memo submitted	Active-step approvers
build_advance_email(memo, workflow_def, step, instance, review_url)	Step completed, next step starts	Next-step approvers
build_action_email(memo, instance, action, actor_name)	Rejection/return/final approval	Memo submitter
HTML template: Inline CSS (email clients strip <style> blocks), clean professional design with:
- DMS header/logo area
- Memo title as heading
- Key-value details table (Workflow, Step, Mode, Date)
- Prominent "Review Memo" CTA button (links to review_url)
- Footer with "This is an automated notification from DMS"
Text fallback: Plain text version of the same content for email clients that don't render HTML.
Step 4: Email Service
New file: notifications/service.py
class EmailService:
    def __init__(self, session: Session):
        self.session = session

    def _send_smtp(self, to_email, subject, html_body, text_body) -> bool:
        """Core SMTP send. Returns True on success, False on failure.
        Never raises exceptions."""
        # smtplib.SMTP or smtplib.SMTP_SSL based on SMTP_USE_TLS
        # Login with SMTP_USERNAME/SMTP_PASSWORD
        # Build MIME message (multipart/alternative with text + html)
        # Send and close connection
        # Return True/False

    def _is_already_sent(self, instance_id, step_order, recipient_id, notif_type) -> bool:
        """Idempotency check against email_notifications table."""

    def _record_send(self, instance_id, step_order, recipient_id, notif_type, status, error=None):
        """Write EmailNotification record + AuditService log."""

    def resolve_recipients(self, step: WorkflowStep, document: Document) -> List[User]:
        """Delegate to approval_policy.resolve_eligible_user_ids, then fetch User objects."""
        # Reuses existing approval_policy.py logic

    def send_workflow_notification(self, ..., background_tasks: BackgroundTasks):
        """Enqueue a notification as a background task."""
Step 5: Background Task Function
New file: notifications/tasks.py
Module-level function callable by BackgroundTasks.add_task():
def send_notification_task(
    notification_type: str,
    instance_id: int,
    document_id: int,
    step_order: Optional[int] = None,
):
    """
    Runs in background thread. Creates its own DB session.
    Resolves recipients, checks idempotency, sends emails, logs results.
    """
    from core.database import engine
    with Session(engine) as session:
        # 1. Fetch instance, step, document, workflow definition
        # 2. Resolve recipients based on notification_type
        # 3. For each recipient: check idempotency → build email → send → record result
Why a module-level function: BackgroundTasks.add_task() serializes arguments as simple types (ints, strings), so the function must be importable at module level and create its own session.
Step 6: Integration into Workflow Services
File: workflow/instance_service.py
Modify submit_instance() signature to accept background_tasks: BackgroundTasks. After the commit + refresh at step 12-13, enqueue the notification:
background_tasks.add_task(
    send_notification_task,
    notification_type="submit",
    instance_id=instance.id,
    document_id=document.id,
    step_order=first_step.step_order,
)
File: workflow/approval_service.py
Modify act_on_instance() signature to accept background_tasks: BackgroundTasks. Three integration points:
1. Step advancement (in _advance_step or after it's called): enqueue notification_type="advance", step_order=next_step.step_order
2. REJECT/RETURN: enqueue notification_type="action", no step_order needed
3. APPROVE (final step, no next step): enqueue notification_type="approved"
File: workflow/router.py
Update submit_workflow_instance and act_on_workflow_instance handlers to accept background_tasks: BackgroundTasks = Depends() and pass it to the service methods.
Step 7: Audit Integration
File: audit/models.py
Add to AuditAction enum:
EMAIL_SENT   = "email_sent"
EMAIL_FAILED = "email_failed"
In EmailService._record_send():
AuditService(self.session).log_event(
    action=AuditAction.EMAIL_SENT if status == "sent" else AuditAction.EMAIL_FAILED,
    module=AuditModule.WORKFLOW,
    entity_name="email_notification",
    entity_id=str(notification_id),
    description=f"Email {status}: {notification_type} for instance {instance_id}",
    is_success=(status == "sent"),
    failure_reason=error,
)
Step 8: Tests
New file: tests/test_notifications.py
All tests mock smtplib.SMTP — no real SMTP connections.
#	Test	Assertion
1	Parallel submit notifies all step-1 approvers	Email sent to every eligible user for step 1
2	Sequential submit notifies only step-1 approvers	Emails sent only to step-1 approvers, not step 2+
3	Step completion notifies next-step approvers	After step 1 approved, step-2 approvers receive email
4	Final approval notifies submitter	After last step approved, submitter receives confirmation
5	Rejection notifies submitter	On reject, submitter receives email with remarks
6	Return notifies submitter	On return, submitter receives email with remarks
7	Email failure does not affect workflow state	Mock SMTP to raise, assert instance status transitions correctly
8	Idempotency prevents duplicate emails	Submit twice, assert only one email per recipient
9	Role-based approvers resolved	Approver configured by role → users with that role receive email
10	User-based approvers resolved	Approver configured by user_id → only that user receives email
11	User level filtering applied	Approver without matching user level does NOT receive email
12	Re-submit after return re-triggers notifications	Return → re-submit → step-1 approvers notified again
Test fixtures: Reuse existing conftest.py fixtures (client, session, seed_data). Add a mock_smtp fixture that patches smtplib.SMTP.
Step 9: Frontend (Optional, Minimal)
Per spec: "Display notification status only if the backend exposes it."
Optional: Add GET /api/v1/workflow-instances/{id}/notifications endpoint in workflow/router.py that returns EmailNotification records for an instance. Frontend can show a small "Emails sent" badge on the memo detail page.
No other frontend changes required — the existing submission and approval UIs work unchanged.
File Inventory
Action	File
New	notifications/__init__.py
New	notifications/models.py
New	notifications/service.py
New	notifications/templates.py
New	notifications/tasks.py
New	tests/test_notifications.py
New	migrations/versions/20260826_<rev>_add_email_notifications_table.py
Modify	core/config.py — add SMTP settings
Modify	.env.example — add SMTP section
Modify	audit/models.py — add EMAIL_SENT, EMAIL_FAILED actions
Modify	workflow/instance_service.py — add background_tasks param to submit_instance()
Modify	workflow/approval_service.py — add background_tasks param to act_on_instance()
Modify	workflow/router.py — pass BackgroundTasks to service methods
Modify	migrations/env.py — add import notifications.models
Implementation Order
 1. core/config.py + .env.example — SMTP settings (no dependencies)
 2. notifications/__init__.py + notifications/models.py — tracking table
 3. audit/models.py — add EMAIL_SENT, EMAIL_FAILED
 4. migrations/env.py — add notifications import
 5. Alembic migration — generate and review
 6. notifications/templates.py — email content builders (no dependencies beyond models)
 7. notifications/service.py — EmailService (depends on 1, 2, 3, 6)
 8. notifications/tasks.py — background task function (depends on 7)
 9. workflow/instance_service.py — hook submit_instance() (depends on 8)
10. workflow/approval_service.py — hook act_on_instance() (depends on 8)
11. workflow/router.py — pass BackgroundTasks (depends on 9, 10)
12. tests/test_notifications.py — verify all scenarios
Steps 1-5 can be done in parallel. Steps 6-8 are sequential. Steps 9-11 are sequential. Step 12 comes last.