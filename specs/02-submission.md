# Spec: Submission

## Overview
Phase 2 of the Approval Workflow System implements the runtime submission and approval engine. Users (Makers) submit documents for approval against an active workflow definition, creating a WorkflowInstance that tracks the document through its approval lifecycle. Approvers (Checkers) see a pending queue of instances awaiting their action and can approve, reject, return, clarify, or forward. Every state transition is recorded in an immutable workflow_history ledger. This phase depends on Phase 1 (Foundation) being complete — the workflow_definitions, workflow_steps, and workflow_step_approvers tables and the WorkflowDefinitionService must already exist.

## Depends on
- Phase 1: Foundation (`workflow/` module, `WorkflowDefinitionService`, workflow_definitions/steps/approvers tables)
- `documents/` module — workflow instances reference documents via FK
- `users/` module — submitters and approvers are existing users
- `categories/` module — workflow definitions are scoped to categories
- `user_levels/` module — approver eligibility is filtered by user level visibility
- `audit/` module — every workflow action must also log an audit event

## Routes
### Workflow Instances
- `POST /api/v1/workflow-instances` — submit a document for approval (logged-in, requires `create` permission)
- `GET /api/v1/workflow-instances/pending` — pending approvals for current user (logged-in)
- `GET /api/v1/workflow-instances/mine` — instances submitted by current user (logged-in)
- `GET /api/v1/workflow-instances/{id}` — get instance detail with current step info (logged-in)
- `POST /api/v1/workflow-instances/{id}/actions` — approve/reject/return/clarify/forward (logged-in, approver only)

## Database changes
### New table: `workflow_instances`
| Column | Type | Constraints |
|--------|------|-------------|
| id | int | PK, auto |
| document_id | int | FK → documents.id, not null, indexed |
| workflow_definition_id | int | FK → workflow_definitions.id, not null, indexed |
| current_step_order | int | not null, default 1 |
| status | varchar(30) | not null, default 'submitted', indexed |
| submitted_by | int | FK → users.id, not null |
| submitted_at | datetime | not null, default utcnow |
| updated_at | datetime | not null, default utcnow |

Status enum values: `submitted`, `pending_approval`, `returned`, `rejected`, `approved`

### New table: `workflow_actions`
| Column | Type | Constraints |
|--------|------|-------------|
| id | int | PK, auto |
| workflow_instance_id | int | FK → workflow_instances.id, not null, indexed |
| workflow_step_id | int | FK → workflow_steps.id, not null |
| acted_by | int | FK → users.id, not null |
| action | varchar(20) | not null |
| remarks | varchar(2000) | nullable |
| acted_at | datetime | not null, default utcnow |
| signature_id | int | nullable (FK added in Phase 3) |

Action enum values: `approve`, `reject`, `return`, `clarify`, `forward`

### New table: `workflow_history`
| Column | Type | Constraints |
|--------|------|-------------|
| id | int | PK, auto |
| workflow_instance_id | int | FK → workflow_instances.id, not null, indexed |
| event_type | varchar(50) | not null |
| actor_id | int | FK → users.id, not null |
| designation_snapshot | varchar(100) | nullable (role name at time of event) |
| remarks | varchar(2000) | nullable |
| status_snapshot | varchar(30) | not null |
| occurred_at | datetime | not null, default utcnow |

Append-only — no PUT/PATCH/DELETE endpoints. Mirrors `audit/` immutability pattern.

### Imports in `core/database.py`
Add `import workflow.models` — already present from Phase 1. No additional import needed.

## Templates
No Jinja2 templates — frontend is React/Vite SPA.

## Files to change
- `workflow/models.py` — add WorkflowInstance, WorkflowAction, WorkflowHistory table models + Pydantic read schemas
- `workflow/schemas.py` — add request schemas for submit, action, and query params
- `workflow/service.py` — add WorkflowInstanceService and ApprovalActionService classes
- `workflow/router.py` — add new instance endpoints, mount at `/api/v1/workflow-instances`
- `main.py` — mount the instance router (or extend existing workflow router with a second prefix)
- `middleware/rbac.py` — add new entries to ROUTE_PERMISSION_MAP for workflow-instances
- `audit/models.py` — add SUBMIT_WORKFLOW, APPROVE_WORKFLOW, REJECT_WORKFLOW, RETURN_WORKFLOW, FORWARD_WORKFLOW actions
- `tests/conftest.py` — ensure workflow.models is imported so test DB has the new tables

## Files to create
- `dms-app/src/api/workflowApi.ts` — add instance API functions (extend existing file)
- `dms-app/src/pages/SubmittedDocumentsPage.tsx` — my submitted instances list
- `dms-app/src/pages/PendingApprovalPage.tsx` — pending approvals queue
- `dms-app/src/pages/ApprovalHistoryPage.tsx` — approval history for an instance

## New dependencies
No new dependencies.

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`, `workflow/`)
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py`
- Use SQLModel / parameterized queries only
- Use JWT access + refresh token auth (`core/security.py`)
- Python: 4-space indent, `snake_case`
- TypeScript: 2-space indent, `PascalCase` components, `camelCase` hooks/stores
- Frontend API files import `apiClient` from `./client`, not `apiRoot` from `./base`
- Never expose secrets or sensitive data in logs
- Use `.env` for configuration only (never commit `.env`)
- Maintain audit trail via `AuditService.log_event()` (`audit/service.py`)
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints)
- Tests use SQLite in-memory; patch `engine` in `core.database`, `middleware.rbac`, `middleware.audit`
- Azure AD: use `cryptography` library for JWK parsing (not `jwk.construct()`)
- No new dependencies unless explicitly approved
- Add/update tests for every implemented feature
- Approver eligibility is enforced via `workflow_step_approvers`, on top of RBAC, not instead of it
- An approver who cannot view the underlying document per their user level must not appear as a valid approver for that instance
- Every `workflow_actions` write must also call `AuditService.log_event()` — do not build a second audit mechanism
- workflow_history is append-only (no PUT/PATCH/DELETE endpoints), mirrors audit/ immutability pattern
- Workflow instances snapshot the definition's steps at creation time — definition changes do not affect running instances
- The submitter cannot approve their own instance (self-approval blocked)
- Sequential mode: step completes only after ALL approvers at that step have acted
- Parallel mode: step completes when ANY ONE approver at that step has acted
- When a step completes, the instance advances to the next step_order
- When the final step completes, status becomes `approved`
- `return` sends the instance back to the submitter (status=`returned`), the submitter can re-submit
- `reject` permanently fails the instance (status=`rejected`)
- `clarify` is a no-op status change that lets the approver request more information without advancing or returning
- `forward` reassigns the action to another eligible approver (not implemented in this phase — stub only)
- Admin bypasses all user level restrictions
- Reuse existing role permission matrix (`view`, `download`, `create`, `update`, `delete`) — do not invent new permission verbs

## Definition of done
- [ ] Three new tables (`workflow_instances`, `workflow_actions`, `workflow_history`) created via Alembic migration or DEBUG=True auto-create
- [ ] `POST /api/v1/workflow-instances` creates an instance with status `submitted`, snapshots the definition steps
- [ ] `GET /api/v1/workflow-instances/pending` returns instances where the current user is an eligible approver
- [ ] `GET /api/v1/workflow-instances/mine` returns instances submitted by the current user
- [ ] `GET /api/v1/workflow-instances/{id}` returns instance detail with current step and action history
- [ ] `POST /api/v1/workflow-instances/{id}/actions` with `approve` advances the instance or completes it
- [ ] `POST /api/v1/workflow-instances/{id}/actions` with `reject` sets status to `rejected`
- [ ] `POST /api/v1/workflow-instances/{id}/actions` with `return` sets status to `returned`
- [ ] Sequential approval mode: step completes only after all approvers have acted
- [ ] Parallel approval mode: step completes when any one approver has acted
- [ ] Self-approval is blocked (submitter cannot approve their own instance)
- [ ] User level visibility is enforced (approvers without document access are excluded)
- [ ] workflow_history records every state transition (append-only)
- [ ] Audit events logged for submit, approve, reject, return actions
- [ ] Tests pass: pytest (SQLite in-memory, all existing + new workflow instance tests green)
- [ ] Frontend workflowApi.ts instance functions compile with no TypeScript errors
