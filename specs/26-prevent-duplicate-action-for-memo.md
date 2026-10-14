# Spec: Prevent Duplicate Action for Memo

## Overview

Memos are approved through the shared workflow approval endpoint
(`POST /api/v1/workflow-instances/{id}/actions`), which since commit `8d890be`
rejects a repeated identical action by the same approver at the same workflow
step with HTTP 409 and the message "This record is already approved by the
first approver.", backed by a unique constraint on
`workflow_actions (workflow_instance_id, workflow_step_id, acted_by, action)`.
That guard was specified and tested for Correspondence/OUTBOUND flows; this
step closes the remaining gaps for Memos: add memo-specific backend tests
proving the duplicate protection holds on memo workflow instances, and bring
`MemoDetailPage.tsx` to parity with `CorrespondenceDetailPage.tsx` so the UI
proactively disables actions the current user has already performed at the
current step and surfaces the required warning as a top-center toast instead
of silently letting the user hit the 409.

## Depends on

- Step 01 — Approval Workflow System (workflow instances, steps, `workflow_actions`).
- Step 04 — Frontend Approval Workflow (memo approval UI in `MemoDetailPage.tsx`).
- Step 13 — Single Review Form (memo action modal).
- The duplicate-action backend guard already merged in commit `8d890be`
  (`ApprovalActionService._ensure_no_duplicate_action`, unique constraint
  `uq_workflow_actions_instance_step_user_action`, migration
  `20260930_c5e8f1a2b7d4`). This spec builds on it — it does not rebuild it.

## Routes

No new routes.

Existing route reused: `POST /api/v1/workflow-instances/{instance_id}/actions`
— logged-in, `UPDATE` permission (already in `ROUTE_PERMISSION_MAP`,
`middleware/rbac.py`).

## Database changes

No database changes.

Already in place from commit `8d890be` (verified against
`workflow/models.py` + `core/database.py` metadata):
- Unique constraint `uq_workflow_actions_instance_step_user_action` on
  `workflow_actions (workflow_instance_id, workflow_step_id, acted_by, action)`.
- Applied via `migrations/versions/20260930_c5e8f1a2b7d4_unique_workflow_action_per_step.py`
  (head `c5e8f1a2b7d4`).

## Templates

No Jinja2 templates — frontend is React/Vite SPA.

## Files to change

- `dms-app/src/pages/MemoDetailPage.tsx`
  - Fetch already provides `WorkflowInstanceDetail` (`actions`,
    `current_step_id`); compute `actedAtCurrentStep(action)` from
    `instance.actions` where `acted_by === user.id`,
    `workflow_step_id === instance.current_step_id`.
  - In the "Take Action" modal, disable the approve/reject/return option (or
    the Confirm button) for actions already performed by the current user at
    the current step; show a short hint ("You have already approved this
    step...") when the current user's approve is already recorded.
  - Error toast: show the backend `detail` verbatim at the top of the UI via
    `toast.error(message, { position: 'top-center' })` (falls back to
    `getErrorMessage(err)`), so the 409 message
    "This record is already approved by the first approver." is visible.
  - Keep the existing `acting` in-flight guard; refresh `instance` + `memo`
    after each action (already done).
  - Import `user` from `useAuthStore` for the `acted_by` comparison.
- `tests/test_memos.py`
  - New test class for duplicate-action protection on memo workflow instances
    (see Definition of done).

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- Use FastAPI + SQLModel only.
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`).
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router).
- Keep routers thin; business logic belongs in services.
- Use `CurrentUser` from `core/dependencies.py` for user injection.
- Use `AdminUser` for admin-only endpoints.
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` (this spec adds no new endpoints — the memo action endpoint is already mapped to `UPDATE`).
- Use SQLModel / parameterized queries only.
- Use JWT access + refresh token auth (core/security.py).
- Hash passwords with bcrypt 4.0.1 (do not upgrade).
- Python: 4-space indent, `snake_case`.
- TypeScript: 2-space indent, `PascalCase` components, `camelCase` hooks/stores.
- Frontend API files import `apiClient` from `./client`, not `apiRoot` from `./base`.
- Never expose secrets or sensitive data in logs.
- Use `.env` for configuration only (never commit `.env`).
- Maintain audit trail via `AuditService.log_event()` (audit/service.py).
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints).
- Tests use SQLite in-memory; patch `engine` in `core.database`, `middleware.rbac`, `middleware.audit`.
- Azure AD: use `cryptography` library for JWK parsing (not `jwk.construct()`).
- No new dependencies unless explicitly approved.
- Add/update tests for every implemented feature.
- **Memo-specific:**
  - Do NOT create a separate memo approval mechanism — memo approvals must
    keep going through `ApprovalActionService.act_on_instance`
    (`workflow/approval_service.py`), which already enforces the duplicate
    guard for all modules.
  - Do NOT weaken or duplicate the unique constraint
    `uq_workflow_actions_instance_step_user_action`; the DB constraint is the
    race backstop and the service pre-check provides the friendly 409.
  - The approve rejection message must be surfaced verbatim:
    "This record is already approved by the first approver." (other actions:
    "You have already performed '<action>' on this step.").
  - Preserve memo behavior: `_check_edit_access` rules (terminal statuses
    frozen, author edits non-terminal, eligible approvers only in
    draft/returned/rejected), publish flow, markdown → PDF generation
    (`memos/pdf_generator.py`), TipTap rendering, signature display.
  - Preserve Sequential/Parallel semantics, RBAC, company scoping, User Level
    visibility, audit, notifications, and `workflow_history` — the duplicate
    guard must not change who may act or when a step advances.
  - Frontend toast placement for approval errors:
    `{ position: 'top-center' }` per-call override (do not move the global
    `<Toaster>` in `main.tsx`).

## Definition of done

1. Approve a memo once via
   `POST /api/v1/workflow-instances/{id}/actions` → 200; exactly one
   `workflow_actions` row exists for that instance/step/user/action.
2. The same approver repeats the approve → HTTP 409 with
   `detail == "This record is already approved by the first approver."`,
   and the `workflow_actions` row count is still 1 (asserted in
   `tests/test_memos.py`).
3. A fresh session re-attempt (page refresh equivalent) is also rejected —
   the check is server-side state, not in-memory UI state.
4. The next sequential approver can still approve the memo normally
   (step completes / advances as before).
5. Repeat `return`/`clarify` on the same step → 409 with the
   `'<action>'` message; `clarify` followed by `approve` remains allowed;
   reject/return of a memo still work.
6. Parallel-mode memo approval remains unaffected (first approve completes
   the step; other approvers are not blocked at a *different* step).
7. In `MemoDetailPage.tsx`, after the current user approves, reopening the
   "Take Action" modal disables/hides the already-performed action and shows
   the hint; if the server still rejects (race), the toast appears at the
   top-center of the UI with the exact 409 message.
8. Memo edit/publish/download-PDF flows still work
   (`pytest tests/test_memos.py` fully green, including new tests).
9. Full backend suite shows no regressions
   (pre-existing failures `test_parallel_step_any_approve_completes`,
   `test_superadmin_cannot_modify_category_ids`, and the 14
   `test_document_visibility` errors are unrelated and unchanged).
10. `cd dms-app && npm run build` passes (typecheck) and `npm run lint`
    reports no new errors versus baseline.
