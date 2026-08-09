# Spec: Approval Workflow System — Phase 1: Foundation

## Overview
This feature introduces a generic, document-type-agnostic approval engine into the DMS. Phase 1 establishes the foundation: a new `workflow/` backend module that lets admins define multi-step approval workflows tied to document categories, with configurable sequential or parallel approval modes and per-step approver assignment by user or role. No runtime approval actions are included in this phase — only the template/configuration layer. This is the first step of a five-phase roadmap outlined in AGENTS.md.

## Depends on
- `documents/` module (existing) — workflows reference documents via category
- `categories/` module (existing) — workflows are scoped to a document category
- `users/` module (existing) — approvers are assigned by user or role
- `roles` system (existing) — role-based approver assignment
- `user_levels/` module (existing) — user level visibility rules apply to document access
- `audit/` module (existing) — workflow config changes must be audited

## Routes
### Workflow Definitions (admin-only)
- `POST /api/v1/workflows` — create a new workflow definition with steps and approvers — admin
- `GET /api/v1/workflows` — list all workflow definitions (with stats) — logged-in
- `GET /api/v1/workflows/{id}` — get workflow definition detail with steps and approvers — logged-in
- `PUT /api/v1/workflows/{id}` — update workflow definition, steps, or approvers — admin
- `DELETE /api/v1/workflows/{id}` — soft-delete (deactivate) a workflow definition — admin
- `PATCH /api/v1/workflows/{id}/activate` — reactivate a deactivated workflow — admin

### Workflow Steps (admin-only, nested under workflows)
- `GET /api/v1/workflows/{id}/steps` — list steps for a workflow definition — logged-in
- `PUT /api/v1/workflows/{id}/steps` — replace all steps for a workflow definition (full replace) — admin

## Database changes
### New table: `workflow_definitions`
| Column | Type | Constraints |
|--------|------|-------------|
| id | int | PK, auto |
| name | varchar(255) | not null, unique, indexed |
| description | varchar(1000) | nullable |
| document_category_id | int | FK → categories.id, not null, indexed |
| is_active | bool | default true, indexed |
| created_by | int | FK → users.id, not null |
| created_at | datetime | default utcnow |
| updated_at | datetime | default utcnow |

### New table: `workflow_steps`
| Column | Type | Constraints |
|--------|------|-------------|
| id | int | PK, auto |
| workflow_definition_id | int | FK → workflow_definitions.id, not null, indexed |
| step_order | int | not null |
| step_name | varchar(255) | not null |
| approval_mode | enum('sequential','parallel') | default 'sequential' |
| is_active | bool | default true |

Unique constraint: (workflow_definition_id, step_order)

### New table: `workflow_step_approvers`
| Column | Type | Constraints |
|--------|------|-------------|
| id | int | PK, auto |
| workflow_step_id | int | FK → workflow_steps.id, not null, indexed |
| user_id | int | FK → users.id, nullable |
| role_id | int | FK → roles.id, nullable |
| priority | int | default 0, not null |
| is_active | bool | default true |

Constraint: exactly one of user_id or role_id must be non-null (enforced in service layer).

### Relationships added
- `WorkflowDefinition` → `Category` (many-to-one via document_category_id)
- `WorkflowDefinition` → `User` (many-to-one via created_by)
- `WorkflowDefinition` → `WorkflowStep` (one-to-many)
- `WorkflowStep` → `WorkflowDefinition` (many-to-one)
- `WorkflowStep` → `WorkflowStepApprover` (one-to-many)
- `WorkflowStepApprover` → `WorkflowStep` (many-to-one)
- `WorkflowStepApprover` → `User` (many-to-one, nullable)
- `WorkflowStepApprover` → `Role` (many-to-one, nullable)

### Imports in `core/database.py`
Add `import workflow.models` to `create_db_and_tables()` so SQLModel metadata includes the new tables.

## Templates
No Jinja2 templates — frontend is React/Vite SPA.

## Files to change
- `main.py` — import and register `workflow_router` at `/api/v1/workflows`
- `core/database.py` — add `import workflow.models` in `create_db_and_tables()`
- `middleware/rbac.py` — add workflow endpoints to `ROUTE_PERMISSION_MAP`:
  - `(POST, "/api/v1/workflows")` → `PermissionAction.CREATE` (admin config)
  - `(PUT, "/api/v1/workflows")` → `PermissionAction.UPDATE` (admin config)
  - `(DELETE, "/api/v1/workflows")` → `PermissionAction.DELETE` (admin config)
- `audit/models.py` — add `WORKFLOW` to `AuditModule` enum, add workflow-specific `AuditAction` values (`CREATE_WORKFLOW`, `UPDATE_WORKFLOW`, `DELETE_WORKFLOW`, `ACTIVATE_WORKFLOW`)

## Files to create
### Backend
- `workflow/__init__.py` — empty
- `workflow/models.py` — SQLModel table models (`WorkflowDefinition`, `WorkflowStep`, `WorkflowStepApprover`) + Pydantic read schemas (`WorkflowDefinitionRead`, `WorkflowStepRead`, `WorkflowStepApproverRead`, `WorkflowDefinitionListResponse`)
- `workflow/schemas.py` — request/response schemas (`WorkflowDefinitionCreate`, `WorkflowDefinitionUpdate`, `WorkflowStepCreate`, `WorkflowStepApproverCreate`, `WorkflowDefinitionDetailRead`)
- `workflow/service.py` — `WorkflowDefinitionService` class (CRUD, takes `Session`):
  - `create_definition(data, current_user)` → create definition + steps + approvers
  - `get_definition(definition_id)` → detail with steps and approvers
  - `list_definitions(skip, limit, category_id, is_active)` → paginated list
  - `update_definition(definition_id, data, current_user)` → full update of definition/steps/approvers
  - `deactivate_definition(definition_id)` → soft-delete
  - `activate_definition(definition_id)` → reactivate
  - All write operations call `AuditService.log_event()`
- `workflow/router.py` — FastAPI router with all endpoints listed above

### Frontend
- `dms-app/src/api/workflowApi.ts` — API client functions using `apiClient` from `./client`

## New dependencies
No new dependencies. This phase uses only existing packages (FastAPI, SQLModel, Pydantic).

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules follow: `models.py`, `schemas.py`, `service.py`, `router.py`)
- Keep routers thin; business logic belongs in `WorkflowDefinitionService`
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints (workflow config is admin-only)
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
- Approval mode enum: `sequential` (step completes only after all approvers act) or `parallel` (step completes when any approver acts)
- Exactly one of `user_id` or `role_id` must be set per approver entry — enforce in service layer, not DB constraint
- Workflow names must be unique
- Step order must be unique within a workflow definition
- Soft-delete via `is_active = false` — never hard-delete workflow definitions (referenced by instances in later phases)
- Only admin users can create, update, or deactivate workflow definitions

## Definition of done
- [ ] `workflow/` module created with `__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py`
- [ ] Three new tables (`workflow_definitions`, `workflow_steps`, `workflow_step_approvers`) created via Alembic migration or `DEBUG=True` auto-create
- [ ] `POST /api/v1/workflows` creates a workflow with steps and approvers (admin-only, returns 403 for non-admins)
- [ ] `GET /api/v1/workflows` returns paginated list of active workflow definitions
- [ ] `GET /api/v1/workflows/{id}` returns definition detail with steps and approvers
- [ ] `PUT /api/v1/workflows/{id}` replaces steps and approvers (admin-only)
- [ ] `DELETE /api/v1/workflows/{id}` soft-deactivates a workflow (admin-only)
- [ ] `PATCH /api/v1/workflows/{id}/activate` reactivates a workflow (admin-only)
- [ ] `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` includes all new workflow endpoints
- [ ] Audit events logged for all write operations (create, update, delete, activate)
- [ ] Tests pass: `pytest` (SQLite in-memory, all existing + new workflow tests green)
- [ ] Frontend `workflowApi.ts` compiles with no TypeScript errors: `npm run build`
