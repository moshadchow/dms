# Email Notification System for Memo Approval Workflow

## Overview

Implement a production-grade email notification system for the DMS Memo Approval Workflow.

When a Maker submits a Memo for approval, automatically send email notifications to the approval authorities defined in the configured Workflow.

## Approval Modes

### Parallel Approval

If the active workflow step uses:

```
Approval Mode = Parallel
```

Send notifications to all approval authorities assigned to the active step simultaneously.

```
Maker
  │
  ▼
Submit for Approval
  │
  ▼
Parallel Step 1
  ├──► Approver A 📧
  ├──► Approver B 📧
  └──► Approver C 📧
```

### Sequential Approval

If the workflow uses:

```
Approval Mode = Sequential
```

Only notify approvers belonging to the current active step.

```
Maker
  │
  ▼
Submit for Approval
  │
  ▼
Step 1
  ├──► Approver A 📧
  └──► Approver B 📧
          │
          ▼
     Step 1 Approved
          │
          ▼
       Step 2
     ┌────┴────┐
     ▼         ▼
Approver C  Approver D
    📧          📧
```

- Step 2 and subsequent approvers must not receive notifications before their step becomes active.
- After Step 1 is successfully completed, notify the authorities of Step 2.
- Continue this process until the final approval.

## Backend Requirements

- Integrate notifications with the existing `WorkflowInstanceService` and `ApprovalActionService`.
- Resolve recipients from the configured `workflow_steps` and `workflow_step_approvers`.
- Do not hardcode approvers, roles, or email addresses.
- Respect existing RBAC and approver eligibility rules.
- Use the existing notification/email infrastructure if available; otherwise implement a reusable email service.
- Email delivery must be asynchronous/background where appropriate.
- Email failure must not roll back a successful Memo submission or approval action.
- Implement retry-safe/idempotent notification handling to prevent duplicate emails.
- Configure SMTP credentials through environment variables.
- Never hardcode or commit email credentials.

## Email Content

The notification should contain relevant information such as:

- Memo Title
- Submitted By
- Workflow Name
- Current Step
- Approval Mode
- Submission Date/Time
- Link to Review/Approve the Memo

Do not expose sensitive Memo content or attachments directly in the email unless explicitly required.

## Frontend Requirements

- Ensure the existing Memo submission and approval UI works correctly with the notification system.
- Display notification status only if the backend exposes it.
- Do not implement notification business logic in React.
- Reuse the existing API client, workflow APIs, authentication, RBAC, and UI architecture.

## Audit & Logging

- Reuse the existing centralized audit mechanism.
- Log email delivery failures and retries appropriately.
- Do not create a separate audit mechanism.

## Testing

Verify:

- Parallel workflow → all active-step approvers receive email.
- Sequential workflow → only Step-1 approvers receive the initial email.
- Step 1 completion → Step-2 approvers receive email.
- Subsequent steps follow the same sequence.
- Future sequential approvers receive no premature notification.
- Final approval does not trigger unnecessary notifications.
- Email failure does not affect workflow state.
- Duplicate emails are prevented.
- User-based and role-based approvers work correctly.

## Acceptance Criteria

- Email notification is automatically triggered on Memo submission.
- Parallel approval notifies all eligible approvers in the active step.
- Sequential approval notifies only the active step.
- Next-step notifications are triggered only after the previous step is completed.
- Recipients come exclusively from the configured Workflow Definition.
- Notifications are asynchronous, retry-safe, and idempotent.
- Existing Memo, Workflow, RBAC, User Level, and Audit functionality remains unaffected.

## Final Approval Notification

## After the Memo receives **final approval**

- Send a confirmation email to the **Maker/Submitter**.
- The email should confirm that the Memo has been successfully approved.
- Include relevant information such as:
  - Memo Title
  - Workflow Name
  - Final Approval Status
  - Approval Date/Time
  - Link to view the approved Memo
- The confirmation email must be triggered only after the workflow reaches its **final approved state**.
- Email delivery failure must not change or roll back the approved workflow status.

## Implementation Notes

- First inspect `AGENTS.md` and the existing workflow implementation before making changes.
- Use the existing Workflow Definition and Workflow Instance state as the single source of truth for determining notification recipients and timing.
- Do not hardcode workflow rules or recipients, and do not modify unrelated functionality.
