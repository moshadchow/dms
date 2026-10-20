# Prompt: Consolidate Pending Approval Actions into a Single Review Form

Act as a **Senior Frontend and Backend Engineer**.

Refactor the existing **Pending Approvals** user interface to consolidate the separate approval actions into a single review workflow.

## Objective

In the Pending Approvals form/page:

- Remove the separate **Approve**, **Reject**, and **Return** buttons from the **Actions** column.
- Replace them with a single button:

```text
Review
```

The existing approval business logic for Approve, Reject, and Return must remain unchanged.

## Required UI Flow

### Pending Approvals List

Current concept:

```text
Actions
├── Approve
├── Reject
└── Return
```

Required:

```text
Actions
└── Review
```

Each pending approval item must have only one Review button.

### Review Form

When the user clicks Review:

```text
Pending Approval List
        ↓
Click Review
        ↓
Open Single Approval Review Form
        ↓
Review Memo Content
Review Attachments
Review Workflow Information
Enter Remarks (if applicable)
        ↓
Choose Action
```

The Review form must contain all relevant information currently required for an approver to review the Memo before taking action.

At the bottom/end of the single Review form, display the three action buttons:

```text
[ Approve ]   [ Reject ]   [ Return ]
```

### Action Behavior

The functionality of the three actions must remain exactly the same:

**Approve:**

```text
Review Form
      ↓
Click Approve
      ↓
Execute Existing Approve Logic
```

**Reject:**

```text
Review Form
      ↓
Click Reject
      ↓
Execute Existing Reject Logic
```

**Return:**

```text
Review Form
      ↓
Click Return
      ↓
Execute Existing Return Logic
```

Do not duplicate or rewrite the existing backend workflow business logic unless necessary for integration.

Reuse the existing approval APIs, services, validation, workflow state transitions, notifications, and audit mechanisms.

## Frontend Requirements

- Remove individual Approve/Reject/Return buttons from the Pending Approvals table/list.
- Add a single Review button in the Actions column.
- Implement one unified Approval Review form/modal/page.
- Load the existing Memo content, attachments, workflow details, and approval context into the Review form.
- Place Approve, Reject, and Return buttons together at the bottom of the Review form.
- Ensure each button triggers its corresponding existing action.
- Reuse existing components and logic where possible.
- Remove unnecessary duplicate action forms/modals after consolidation.
- Preserve existing validation and remarks behavior for each action.

## Backend Requirements

Existing Approve, Reject, and Return APIs and business rules should remain unchanged unless a minimal API adjustment is required.

Preserve existing:

- Workflow state transitions
- Sequential and Parallel approval logic
- Authorization and RBAC checks
- Notification logic
- Maker notifications
- Audit logging
- Approval history

Do not introduce duplicate workflow action logic.

## Expected User Experience

```text
Pending Approvals
│
├── Memo A ─────────────── [ Review ]
├── Memo B ─────────────── [ Review ]
└── Memo C ─────────────── [ Review ]

                ↓

          Approval Review Form
┌─────────────────────────────────────┐
│ Memo Details                        │
│                                     │
│ Memo Content                        │
│ Attachments                         │
│ Workflow Information                │
│ Approval Remarks                    │
│                                     │
│                                     │
│ [ Approve ] [ Reject ] [ Return ]   │
└─────────────────────────────────────┘
```

## Acceptance Criteria

- [ ] The Actions column contains only one Review button.
- [ ] Approve, Reject, and Return buttons are removed from the Pending Approvals list.
- [ ] Clicking Review opens a single unified Approval Review form.
- [ ] The approver can review Memo content and attachments before taking action.
- [ ] Approve, Reject, and Return buttons are available at the bottom of the Review form.
- [ ] Each action performs its existing workflow functionality correctly.
- [ ] Existing validation and remarks requirements remain unchanged.
- [ ] Workflow transitions remain unchanged.
- [ ] Sequential and Parallel workflow behavior remains unchanged.
- [ ] Existing notification and audit functionality remains unchanged.
- [ ] No duplicate approval business logic is introduced.
- [ ] No unrelated Memo or Approval functionality is modified.

## Final Instruction

First inspect the existing Pending Approvals page, action handlers, approval forms/modals, workflow APIs, and approval action services.

Perform an impact analysis and consolidate only the frontend user experience into a single Review flow. Reuse the existing Approve, Reject, and Return business logic and APIs to ensure the workflow behavior remains unchanged.
