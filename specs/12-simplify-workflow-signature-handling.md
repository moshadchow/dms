# Prompt: Simplify Workflow Signature Handling and Auto-Load Signatures in Final Draft

Act as a **Senior Full-Stack Engineer** and update the existing Memo Approval Workflow signature process.

## Objective

Remove all manual signature upload/selection actions from the approval workflow UI and use the user's centrally managed signature automatically when generating the **Download Final Draft** PDF.

## Required Changes

### 1. Submit for Approval

Remove the following from the **Submit for Approval** section:

- Author/Maker signature upload.
- Wet Signature section.
- Any related signature file selection or upload UI.

The Maker should be able to submit the Memo for approval without manually uploading or selecting a signature.

---

### 2. Pending Approval Actions

Remove the **Signature (Optional)** section from the approval action UI for:

- Approve
- Reject
- Return

Approvers must not manually upload, select, or provide a signature while taking these actions.

---

### 3. Automatic Signature Loading in Final Draft

When the user selects **Download Final Draft**, generate the PDF using signatures automatically loaded from the centrally managed user signature records.

The system must:

- Load the Maker/Author's saved signature automatically.
- Load the signatures of the relevant approvers automatically.
- Use the signature assigned to each user in the existing User Signature Management system.
- Embed the signatures in the appropriate signature locations in the final PDF.
- Associate each signature with the correct user and workflow role/action.
- Preserve the correct workflow approval sequence.

Expected flow:

```text
Maker Creates Memo
        ↓
Submit for Approval
        ↓
No Manual Signature Upload
        ↓
Approvers Take Action
        ↓
No Manual Signature Upload
        ↓
Workflow Completed / Final Approved
        ↓
Download Final Draft
        ↓
Automatically Load User Signatures
        ↓
Generate Final PDF with Embedded Signatures
```

## Backend Requirements

- Remove or disable workflow-specific signature upload handling that is no longer required.
- Do not remove the central User Signature Management functionality.
- Reuse the existing user signature path/reference stored in the database.
- Resolve signatures based on the actual Maker and workflow approvers.
- Ensure the PDF generation process uses backend data as the source of truth.
- Do not rely on temporary frontend signature state.
- Handle users without an assigned signature gracefully according to the existing workflow/business rules.
- Do not break existing approval actions, workflow state transitions, or audit history.

## Frontend Requirements

Remove signature-related UI and state from:

- Submit for Approval.
- Approve action.
- Reject action.
- Return action.

Remove any unnecessary:

- Signature upload controls.
- Wet signature controls.
- Signature validation.
- Temporary signature state.
- Related API calls that are no longer required.

Do not remove signature display or download functionality required for the final draft.

## Important Constraints

- Do not change the existing Workflow Definition, Workflow Steps, or approval logic.
- Do not change Approve, Reject, or Return business rules.
- Do not break the centralized Admin User Signature Management feature.
- Do not delete valid user signatures stored in the system.
- Do not modify unrelated Memo, attachment, RBAC, User Level, or document functionality.
- Reuse the existing backend file storage and signature path mechanism.

## Acceptance Criteria

- [ ] Author/Maker signature upload is removed from Submit for Approval.
- [ ] Wet Signature is removed from Submit for Approval.
- [ ] Signature (Optional) is removed from Approve UI.
- [ ] Signature (Optional) is removed from Reject UI.
- [ ] Signature (Optional) is removed from Return UI.
- [ ] No manual signature upload is required during workflow submission or approval actions.
- [ ] Final Draft automatically loads the Maker's saved signature.
- [ ] Final Draft automatically loads the relevant approvers' saved signatures.
- [ ] Signatures are embedded correctly in the generated PDF.
- [ ] Workflow approval sequence and signature association remain correct.
- [ ] Existing centralized User Signature Management remains functional.
- [ ] Existing Memo and Approval Workflow functionality remains unaffected.

## Final Instruction

First inspect the existing workflow signature flow, approval action components, signature APIs, user signature management implementation, and final PDF generation logic.

Perform a complete impact analysis before making changes. Remove only the manual workflow signature handling and update the Final Draft generation to automatically use centrally stored user signatures.

Avoid unrelated refactoring and preserve all existing workflow functionality.
