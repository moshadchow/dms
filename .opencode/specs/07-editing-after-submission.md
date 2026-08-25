# Prompt: Enable Memo Editing After Submission

## Objective

Add an **Edit** option for a submitted Memo.

The submitted user must be able to modify the Memo **after submission but before final approval**.

## Requirements

### 1. Edit Availability

Show the **Edit** option when:

- Memo is submitted
- AND Memo is not approved

The user must be able to edit:

- Memo content/draft
- Attachments
- Signature information

### 2. Approved Memo

Once the Memo reaches **approved** status, the Memo becomes read-only.

Do not show the Edit option and do not allow modification of:

- Memo content
- Attachments
- Signatures

### 3. Workflow Behavior

When a submitted Memo is edited before approval:

- Preserve the existing workflow instance appropriately.
- Ensure the modified Memo content and attachments are used in the ongoing approval process.
- Ensure signature changes are correctly reflected.
- Do not create duplicate workflow instances unless required by the existing workflow design.
- Do not allow an already-approved Memo to re-enter an editable state.

### 4. Authorization

- Only the original submitting user (Maker) may edit the submitted Memo.
- Existing RBAC and User Level restrictions must remain enforced.

### 5. UI

Add **Edit** to the Memo action menu when the Memo is submitted but not approved.

Expected behavior:

| Status | Edit Allowed |
|---|---|
| Draft | Yes |
| Submitted / Pending Approval | Yes (submitter only) |
| Approved | No — Memo is read-only |

### 6. Backend

Verify and update the backend authorization/business rules so that:

- Submitter can update the Memo before approval.
- Content, attachments, and signatures can be modified before approval.
- Approved Memo cannot be modified.
- Unauthorized users cannot modify the Memo.
- Existing workflow and approval history remain consistent.

## Acceptance Criteria

- [ ] Edit option is available to the original submitter after submission.
- [ ] Submitter can edit Memo content before approval.
- [ ] Submitter can add/remove/update attachments before approval.
- [ ] Submitter can modify signature information before approval.
- [ ] Edited data is reflected in the ongoing approval workflow.
- [ ] Edit is unavailable after approval.
- [ ] Approved Memo cannot be modified through the UI or API.
- [ ] Non-submitters cannot edit the submitted Memo.
- [ ] Existing workflow, RBAC, audit, and Memo functionality remain intact.
