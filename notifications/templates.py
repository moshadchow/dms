from datetime import datetime
from typing import Optional, Tuple

from core.config import settings
from core.security import create_token_pair
from memos.models import MemoDetailRead
from workflow.models import WorkflowDefinitionDetailRead, WorkflowInstanceDetailRead, WorkflowStepRead


def _build_review_url(instance_id: int, user_id: int) -> str:
    """Generate a review link with a short-lived JWT token."""
    # Create a token with instance_id and user_id for approval link
    # Using a custom token type with 7-day expiry
    from core.security import _create_token
    from datetime import timedelta

    token = _create_token(
        subject=str(instance_id),
        token_type="approval_link",
        expires_delta=timedelta(days=7),
    )
    return f"{settings.FRONTEND_URL}/approvals/pending"


def _format_datetime(dt: datetime) -> str:
    """Format datetime for email display."""
    return dt.strftime("%B %d, %Y at %I:%M %p")


def _build_html_template(title: str, content: str) -> str:
    """Wrap content in a consistent HTML email template."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden;">
            <div style="background-color: #2563eb; color: white; padding: 24px; text-align: center;">
                <h1 style="margin: 0; font-size: 24px; font-weight: 600;">Document Management System</h1>
            </div>
            <div style="padding: 32px 24px;">
                {content}
            </div>
            <div style="background-color: #f8fafc; padding: 16px 24px; border-top: 1px solid #e2e8f0; text-align: center;">
                <p style="margin: 0; font-size: 12px; color: #64748b;">
                    This is an automated notification from DMS.<br>
                    Please do not reply to this email.
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def _build_text_template(title: str, content: str) -> str:
    """Build plain text version of email."""
    return f"""
{title}

{content}

---
This is an automated notification from DMS.
Please do not reply to this email.
"""


def build_submit_email(
    memo: MemoDetailRead,
    workflow_def: WorkflowDefinitionDetailRead,
    step: WorkflowStepRead,
    instance: WorkflowInstanceDetailRead,
) -> Tuple[str, str, str]:
    """Build email for memo submission notification to active-step approvers."""
    review_url = _build_review_url(instance.id, 0)  # user_id will be added per-recipient

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">New Memo Submitted for Approval</h2>
        <p style="margin: 0 0 24px; color: #475569;">A new memo has been submitted for your approval.</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155; width: 140px;">Memo Title:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{memo.subject}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Workflow:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{workflow_def.name}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Current Step:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{step.step_name}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Approval Mode:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{step.approval_mode.value.title()}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Submitted:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{_format_datetime(instance.submitted_at)}</td>
            </tr>
        </table>

        <div style="text-align: center; margin: 24px 0;">
            <a href="{review_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px;">Review Memo</a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If the button above doesn't work, copy and paste this link into your browser:<br><span style="word-break: break-all;">{review_url}</span></p>
    """

    text_content = f"""
New Memo Submitted for Approval

A new memo has been submitted for your approval.

Memo Title: {memo.subject}
Workflow: {workflow_def.name}
Current Step: {step.step_name}
Approval Mode: {step.approval_mode.value.title()}
Submitted: {_format_datetime(instance.submitted_at)}

Review Memo: {review_url}
"""

    html = _build_html_template("New Memo for Approval", html_content)
    text = _build_text_template("New Memo for Approval", text_content)

    subject = f"[DMS] New Memo for Approval: {memo.subject}"

    return subject, html, text


def build_advance_email(
    memo: MemoDetailRead,
    workflow_def: WorkflowDefinitionDetailRead,
    step: WorkflowStepRead,
    instance: WorkflowInstanceDetailRead,
) -> Tuple[str, str, str]:
    """Build email for workflow step advancement notification to next-step approvers."""
    review_url = _build_review_url(instance.id, 0)

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">Workflow Advanced to Your Step</h2>
        <p style="margin: 0 0 24px; color: #475569;">A memo has advanced to the next approval step and requires your action.</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155; width: 140px;">Memo Title:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{memo.subject}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Workflow:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{workflow_def.name}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Current Step:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{step.step_name}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Approval Mode:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{step.approval_mode.value.title()}</td>
            </tr>
        </table>

        <div style="text-align: center; margin: 24px 0;">
            <a href="{review_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px;">Review Memo</a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If the button above doesn't work, copy and paste this link into your browser:<br><span style="word-break: break-all;">{review_url}</span></p>
    """

    text_content = f"""
Workflow Advanced to Your Step

A memo has advanced to the next approval step and requires your action.

Memo Title: {memo.subject}
Workflow: {workflow_def.name}
Current Step: {step.step_name}
Approval Mode: {step.approval_mode.value.title()}

Review Memo: {review_url}
"""

    html = _build_html_template("Workflow Advanced to Your Step", html_content)
    text = _build_text_template("Workflow Advanced to Your Step", text_content)

    subject = f"[DMS] Workflow Advanced: {memo.subject}"

    return subject, html, text


def build_action_email(
    memo: MemoDetailRead,
    instance: WorkflowInstanceDetailRead,
    action: str,
    actor_name: str,
    remarks: str = None,
) -> Tuple[str, str, str]:
    """Build email for workflow action (approve/reject/return) notification to submitter."""
    review_url = _build_review_url(instance.id, 0)

    action_lower = action.lower()
    action_titles = {
        "approve": "Approved",
        "reject": "Rejected",
        "return": "Returned",
    }
    action_title = action_titles.get(action_lower, action.title())

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">Memo {action_title}</h2>
        <p style="margin: 0 0 24px; color: #475569;">Your memo has been {action_lower} by {actor_name}.</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155; width: 140px;">Memo Title:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{memo.subject}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Action:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{action_title}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">By:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{actor_name}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Date:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{_format_datetime(datetime.utcnow())}</td>
            </tr>
        </table>

        {f'<div style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 6px; padding: 16px; margin-bottom: 24px;"><p style="margin: 0; font-weight: 600; color: #92400e;">Remarks:</p><p style="margin: 8px 0 0; color: #78350f;">{remarks}</p></div>' if remarks else ''}

        <div style="text-align: center; margin: 24px 0;">
            <a href="{review_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px;">View Memo</a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If the button above doesn't work, copy and paste this link into your browser:<br><span style="word-break: break-all;">{review_url}</span></p>
    """

    text_content = f"""
Memo {action_title}

Your memo has been {action_lower} by {actor_name}.

Memo Title: {memo.subject}
Action: {action_title}
By: {actor_name}
Date: {_format_datetime(datetime.utcnow())}

{f"Remarks: {remarks}" if remarks else ""}

View Memo: {review_url}
"""

    html = _build_html_template(f"Memo {action_title}", html_content)
    text = _build_text_template(f"Memo {action_title}", text_content)

    subject = f"[DMS] Memo {action_title}: {memo.subject}"

    return subject, html, text


def build_password_reset_email(
    user_name: str,
    temp_password: str,
) -> Tuple[str, str, str]:
    """Build email for admin-initiated password reset with temporary password."""

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">Your Password Has Been Reset</h2>
        <p style="margin: 0 0 24px; color: #475569;">Hello {user_name},</p>
        <p style="margin: 0 0 24px; color: #475569;">An administrator has reset your password. You can now log in using the temporary password below:</p>

        <div style="background-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 24px; text-align: center;">
            <p style="margin: 0; font-size: 14px; color: #64748b;">Your temporary password:</p>
            <p style="margin: 8px 0 0; font-size: 20px; font-weight: 700; color: #1e293b; font-family: monospace; letter-spacing: 1px;">{temp_password}</p>
        </div>

        <p style="margin: 0 0 24px; color: #475569;">For your security, you will be required to change this password upon your next login.</p>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If you did not request this change, please contact your administrator immediately.</p>
    """

    text_content = f"""
Your Password Has Been Reset

Hello {user_name},

An administrator has reset your password. You can now log in using the temporary password below:

Temporary password: {temp_password}

For your security, you will be required to change this password upon your next login.

If you did not request this change, please contact your administrator immediately.
"""

    html = _build_html_template("Password Reset", html_content)
    text = _build_text_template("Password Reset", text_content)

    subject = "[DMS] Your Password Has Been Reset"

    return subject, html, text


def build_correspondence_assigned_email(
    reference_number: str,
    subject_line: str,
    direction: str,
    assigned_by: str,
    remarks: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Build email for correspondence assignment notification."""
    view_url = f"{settings.FRONTEND_URL}/correspondence"

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">Correspondence Assigned to You</h2>
        <p style="margin: 0 0 24px; color: #475569;">A {direction} correspondence has been assigned to you for action.</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155; width: 140px;">Reference No:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b; font-family: monospace;">{reference_number}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Subject:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{subject_line}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Direction:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{direction.title()}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Assigned By:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{assigned_by}</td>
            </tr>
        </table>

        {f'<div style="background-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 24px;"><p style="margin: 0; font-weight: 600; color: #334155;">Remarks:</p><p style="margin: 8px 0 0; color: #475569;">{remarks}</p></div>' if remarks else ''}

        <div style="text-align: center; margin: 24px 0;">
            <a href="{view_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px;">View Correspondence</a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If the button above doesn't work, copy and paste this link into your browser:<br><span style="word-break: break-all;">{view_url}</span></p>
    """

    text_content = f"""
Correspondence Assigned to You

A {direction} correspondence has been assigned to you for action.

Reference No: {reference_number}
Subject: {subject_line}
Direction: {direction.title()}
Assigned By: {assigned_by}

{f"Remarks: {remarks}" if remarks else ""}

View Correspondence: {view_url}
"""

    html = _build_html_template("Correspondence Assigned", html_content)
    text = _build_text_template("Correspondence Assigned", text_content)

    subject = f"[DMS] Correspondence Assigned: {reference_number}"

    return subject, html, text


def build_correspondence_dispatched_email(
    reference_number: str,
    subject_line: str,
    direction: str,
    dispatched_by: str,
    dispatch_method: str,
    dispatch_reference: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Build email for correspondence dispatch notification."""
    view_url = f"{settings.FRONTEND_URL}/correspondence"

    dispatch_info = f"Dispatch Reference: {dispatch_reference}" if dispatch_reference else "No dispatch reference provided"

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">Correspondence Dispatched</h2>
        <p style="margin: 0 0 24px; color: #475569;">A {direction} correspondence has been dispatched.</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155; width: 140px;">Reference No:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b; font-family: monospace;">{reference_number}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Subject:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{subject_line}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Direction:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{direction.title()}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Dispatched By:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{dispatched_by}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Method:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{dispatch_method.replace('_', ' ').title()}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Details:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{dispatch_info}</td>
            </tr>
        </table>

        <div style="text-align: center; margin: 24px 0;">
            <a href="{view_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px;">View Correspondence</a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If the button above doesn't work, copy and paste this link into your browser:<br><span style="word-break: break-all;">{view_url}</span></p>
    """

    text_content = f"""
Correspondence Dispatched

A {direction} correspondence has been dispatched.

Reference No: {reference_number}
Subject: {subject_line}
Direction: {direction.title()}
Dispatched By: {dispatched_by}
Method: {dispatch_method.replace('_', ' ').title()}
{dispatch_info}

View Correspondence: {view_url}
"""

    html = _build_html_template("Correspondence Dispatched", html_content)
    text = _build_text_template("Correspondence Dispatched", text_content)

    subject = f"[DMS] Correspondence Dispatched: {reference_number}"

    return subject, html, text


def build_correspondence_submit_email(
    reference_number: str,
    subject_line: str,
    direction: str,
    submitted_by: str,
    workflow_definition: str,
    remarks: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Build email for correspondence submission notification to workflow approvers."""
    view_url = f"{settings.FRONTEND_URL}/correspondence"

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">Correspondence Submitted for Approval</h2>
        <p style="margin: 0 0 24px; color: #475569;">A {direction} correspondence has been submitted and requires your approval.</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155; width: 140px;">Reference No:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b; font-family: monospace;">{reference_number}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Subject:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{subject_line}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Direction:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{direction.title()}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Submitted By:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{submitted_by}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Workflow:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{workflow_definition}</td>
            </tr>
        </table>

        {f'<div style="background-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 24px;"><p style="margin: 0; font-weight: 600; color: #334155;">Remarks:</p><p style="margin: 8px 0 0; color: #475569;">{remarks}</p></div>' if remarks else ''}

        <div style="text-align: center; margin: 24px 0;">
            <a href="{view_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px;">View Correspondence</a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If the button above doesn't work, copy and paste this link into your browser.<br><span style="word-break: break-all;">{view_url}</span></p>
    """

    text_content = f"""
Correspondence Submitted for Approval

A {direction} correspondence has been submitted and requires your approval.

Reference No: {reference_number}
Subject: {subject_line}
Direction: {direction.title()}
Submitted By: {submitted_by}
Workflow: {workflow_definition}
{f"Remarks: {remarks}" if remarks else ""}

View Correspondence: {view_url}
"""

    html = _build_html_template("Correspondence Submitted for Approval", html_content)
    text = _build_text_template("Correspondence Submitted for Approval", text_content)

    subject = f"[DMS] Correspondence Submitted: {reference_number}"

    return subject, html, text


def build_correspondence_action_email(
    reference_number: str,
    subject_line: str,
    direction: str,
    action: str,
    actor_name: str,
    remarks: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Build email for correspondence action (approve/reject/return) notification."""
    view_url = f"{settings.FRONTEND_URL}/correspondence"

    action_titles = {"approve": "Approved", "reject": "Rejected", "return": "Returned"}
    action_title = action_titles.get(action.lower(), action.title())

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">Correspondence {action_title}</h2>
        <p style="margin: 0 0 24px; color: #475569;">Correspondence {reference_number} has been {action.lower()} by {actor_name}.</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155; width: 140px;">Reference No:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b; font-family: monospace;">{reference_number}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Subject:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{subject_line}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Direction:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{direction.title()}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Action:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{action_title}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">By:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{actor_name}</td>
            </tr>
        </table>

        {f'<div style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 6px; padding: 16px; margin-bottom: 24px;"><p style="margin: 0; font-weight: 600; color: #92400e;">Remarks:</p><p style="margin: 8px 0 0; color: #78350f;">{remarks}</p></div>' if remarks else ''}

        <div style="text-align: center; margin: 24px 0;">
            <a href="{view_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px;">View Correspondence</a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If the button above doesn't work, copy and paste this link into your browser.<br><span style="word-break: break-all;">{view_url}</span></p>
    """

    text_content = f"""
Correspondence {action_title}

Correspondence {reference_number} has been {action_lower} by {actor_name}.

Reference No: {reference_number}
Subject: {subject_line}
Direction: {direction.title()}
Action: {action_title}
By: {actor_name}

{f"Remarks: {remarks}" if remarks else ""}

View Correspondence: {view_url}
"""

    html = _build_html_template(f"Correspondence {action_title}", html_content)
    text = _build_text_template(f"Correspondence {action_title}", text_content)

    subject = f"[DMS] Correspondence {action_title}: {reference_number}"

    return subject, html, text


def build_correspondence_completed_email(
    reference_number: str,
    subject_line: str,
    direction: str,
) -> Tuple[str, str, str]:
    """Build email for correspondence completion notification."""
    view_url = f"{settings.FRONTEND_URL}/correspondence"

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">Correspondence Completed</h2>
        <p style="margin: 0 0 24px; color: #475569;">Correspondence {reference_number} has been completed and archived.</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155; width: 140px;">Reference No:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b; font-family: monospace;">{reference_number}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Subject:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{subject_line}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Direction:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{direction.title()}</td>
            </tr>
        </table>

        <div style="text-align: center; margin: 24px 0;">
            <a href="{view_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px;">View Correspondence</a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If the button above doesn't work, copy and paste this link into your browser.<br><span style="word-break: break-all;">{view_url}</span></p>
    """

    text_content = f"""
Correspondence Completed

Correspondence {reference_number} has been completed and archived.

Reference No: {reference_number}
Subject: {subject_line}
Direction: {direction.title()}

View Correspondence: {view_url}
"""

    html = _build_html_template("Correspondence Completed", html_content)
    text = _build_text_template("Correspondence Completed", text_content)

    subject = f"[DMS] Correspondence Completed: {reference_number}"

    return subject, html, text


def build_correspondence_forwarded_email(
    reference_number: str,
    subject_line: str,
    direction: str,
    forwarded_by: str,
    remarks: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Build email for correspondence forward notification."""
    view_url = f"{settings.FRONTEND_URL}/correspondence"

    html_content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px; color: #1e293b;">Correspondence Forwarded to You</h2>
        <p style="margin: 0 0 24px; color: #475569;">A {direction} correspondence has been forwarded to you for review.</p>

        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px;">
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155; width: 140px;">Reference No:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b; font-family: monospace;">{reference_number}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Subject:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{subject_line}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Direction:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{direction.title()}</td>
            </tr>
            <tr>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #334155;">Forwarded By:</td>
                <td style="padding: 12px 0; border-bottom: 1px solid #e2e8f0; color: #1e293b;">{forwarded_by}</td>
            </tr>
        </table>

        {f'<div style="background-color: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; margin-bottom: 24px;"><p style="margin: 0; font-weight: 600; color: #334155;">Remarks:</p><p style="margin: 8px 0 0; color: #475569;">{remarks}</p></div>' if remarks else ''}

        <div style="text-align: center; margin: 24px 0;">
            <a href="{view_url}" style="display: inline-block; background-color: #2563eb; color: white; padding: 14px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 16px;">View Correspondence</a>
        </div>

        <p style="margin: 0; font-size: 14px; color: #64748b;">If the button above doesn't work, copy and paste this link into your browser:<br><span style="word-break: break-all;">{view_url}</span></p>
    """

    text_content = f"""
Correspondence Forwarded to You

A {direction} correspondence has been forwarded to you for review.

Reference No: {reference_number}
Subject: {subject_line}
Direction: {direction.title()}
Forwarded By: {forwarded_by}

{f"Remarks: {remarks}" if remarks else ""}

View Correspondence: {view_url}
"""

    html = _build_html_template("Correspondence Forwarded", html_content)
    text = _build_text_template("Correspondence Forwarded", text_content)

    subject = f"[DMS] Correspondence Forwarded: {reference_number}"

    return subject, html, text