# Prompt: Remove Category Dependency from Workflow Definition

## Objective

Update the Approval Workflow system so that **Workflow Definition no longer contains or depends on a Category dropdown**.

## Requirements

- Remove the **Category** dropdown from the Workflow Definition create/edit UI.
- Remove the frontend state, validation, and API payload handling related to selecting a Category for a Workflow Definition.
- A Workflow Definition's `document_category_id` must not be derived from or dependent on the Memo's category chain (`Memo → document_id → directory_id → directory.category_id`).
- Workflow Definition configuration must be independent of the Memo's Directory/Category relationship.
- Do not automatically populate `document_category_id` from the Memo's category.
- Update the backend API/service/schema/model as necessary to remove this dependency.
- Remove any validation that requires the Workflow Definition's category to match the Memo's category.
- Ensure workflow selection and initiation continue to work correctly without Category-based dependency.

## Important Constraint

Do not change the existing:

- Memo → Document → Directory relationship
- Directory → Category relationship
- Memo creation/editing functionality
- Memo workflow approval process
- Workflow steps and approvers
- RBAC/User Level rules
- Existing workflow history and approval actions

**Only remove the Workflow Definition → Category dependency.**

## Acceptance Criteria

- [ ] Category dropdown is no longer displayed in Workflow Definition create/edit forms.
- [ ] Workflow Definition can be created/updated without selecting a Category.
- [ ] `document_category_id` is no longer populated from the Memo's category.
- [ ] Memo's `document_id → directory_id → category_id` chain remains unchanged.
- [ ] Workflow initiation does not fail because of a Category mismatch.
- [ ] Existing Memo workflow functionality continues to work.
- [ ] No unrelated functionality is modified.
