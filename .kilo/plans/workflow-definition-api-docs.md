# Workflow Definition API Documentation

## 1. Overview

The Workflow Definition APIs provide the administrative layer for configuring, managing, and versioning approval workflow templates within the DMS. These APIs are **Phase 1** of a five-phase approval workflow roadmap (defined in `AGENTS.md`). They define *how* documents flow through approval — not the runtime execution of those flows (that is Phase 2: Workflow Instances).

Every API in this document operates exclusively on the `workflow_definitions`, `workflow_steps`, and `workflow_step_approvers` tables. No workflow instances, approval actions, or signatures are created or modified by these endpoints.

---

## 2. Workflow Definition Concept

A **Workflow Definition** is an administrator-configured, reusable template that describes the approval process for documents within a specific category. It is the *blueprint*, not the *execution*.

A Workflow Definition contains:

```
Workflow Definition
├── name                     — unique human-readable identifier
├── description              — optional context
├── document_category_id     — FK → categories.id (scope)
├── is_active                — whether this definition is available for use
├── created_by               — FK → users.id (admin who created it)
│
└── Steps (1..N, ordered by step_order)
    ├── step_order           — 1-based sequential position
    ├── step_name            — human-readable label
    ├── approval_mode        — "sequential" or "parallel"
    │
    └── Approvers (1..N)
        ├── user_id          — FK → users.id (specific person), OR
        ├── role_id          — FK → roles.id (anyone with this role)
        └── priority         — ordering within the step
```

**Source of truth:** Defined in `AGENTS.md` under "Approval Workflow System — Phase Plan" and implemented in `workflow/models.py:48-66`, `workflow/models.py:79-92`, `workflow/models.py:104-121`.

---

## 3. GET /api/v1/workflows

### Purpose

Retrieve a paginated, filterable list of workflow definitions.

### Usage

Called by the admin UI (WorkflowConfigPage, ApprovalMatrixPage) and any list view that needs to display available workflows. Returns lightweight metadata — no steps or approvers are included (use the detail endpoint for that).

### Access Control

- **Any authenticated user** (uses `CurrentUser` dependency, not `AdminUser`).
- **RBAC middleware:** `GET /api/v1/workflows` has **no entry** in `ROUTE_PERMISSION_MAP` (`middleware/rbac.py:26-41`), so the middleware allows it through. Per-endpoint, `CurrentUser` enforces authentication only — no specific permission verb is checked.
- **Source:** `workflow/router.py:20-36`.

### Request

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `category_id` | int | No | None | Filter by document category |
| `is_active` | bool | No | None | Filter by active/inactive status |
| `skip` | int | No | 0 | Offset for pagination (≥0) |
| `limit` | int | No | 50 | Page size (1–200) |

**Source:** `workflow/router.py:26-29`, `workflow/schemas.py` (query params defined in router, not schemas).

### Response

```json
{
  "total": 12,
  "page": 1,
  "limit": 50,
  "items": [
    {
      "id": 1,
      "name": "Invoice Approval",
      "description": "Two-step invoice review",
      "document_category_id": 1,
      "category_name": "Finance",
      "is_active": true,
      "created_by": 1,
      "created_at": "2026-08-09T10:00:00",
      "updated_at": "2026-08-09T10:00:00"
    }
  ]
}
```

**Note:** `WorkflowDefinitionListResponse` returns `WorkflowDefinitionRead` items, which do **not** include `steps`. The `page` field is computed as `(skip // limit) + 1`.

**Source:** `workflow/models.py:168-172`, `workflow/service.py:236-271`.

### Business Rules

- Results are ordered alphabetically by `name` (`service.py:260`).
- When no filters are provided, all definitions (active and inactive) are returned.
- The `category_name` is resolved via the `Category` relationship (`selectin` eager load).

### Database

- Table: `workflow_definitions`
- Joins: None (direct query).

### Audit

- No audit event. This is a read-only operation.

---

## 4. POST /api/v1/workflows

### Purpose

Create a new workflow definition with its complete step and approver configuration in a single atomic call.

### Usage

Called by an administrator via the Workflow Configuration UI when defining a new approval process. The admin specifies the workflow name, which document category it applies to, and the ordered steps with their approvers.

### Access Control

- **Admin only** (`AdminUser` dependency, `workflow/router.py:46`).
- **RBAC middleware:** `("POST", "/api/v1/workflows") → PermissionAction.CREATE` (`middleware/rbac.py:38`). The admin bypasses RBAC checks (`middleware/rbac.py:117-119`).
- **Source:** `workflow/router.py:39-51`.

### Request

```json
{
  "name": "Invoice Approval",
  "description": "Two-step invoice review process",
  "document_category_id": 1,
  "steps": [
    {
      "step_order": 1,
      "step_name": "Manager Review",
      "approval_mode": "sequential",
      "approvers": [
        { "user_id": 5, "priority": 0 }
      ]
    },
    {
      "step_order": 2,
      "step_name": "Finance Director",
      "approval_mode": "sequential",
      "approvers": [
        { "role_id": 2, "priority": 0 }
      ]
    }
  ]
}
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `name` | string | **Yes** | 2–255 chars, **unique** | Human-readable workflow name |
| `description` | string | No | max 1000 chars | Context for the workflow |
| `document_category_id` | int | **Yes** | FK → categories.id | Category this workflow applies to |
| `steps` | array | **Yes** | min 1 item | Ordered list of approval steps |

**Step object:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `step_order` | int | **Yes** | ≥1, unique within workflow | 1-based position |
| `step_name` | string | **Yes** | 1–255 chars | Human-readable label |
| `approval_mode` | string | No | `"sequential"` (default) or `"parallel"` | How approvers are evaluated |
| `approvers` | array | **Yes** | min 1 item | Who must approve at this step |

**Approver object:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `user_id` | int | Conditionally | mutually exclusive with `role_id` | Specific user |
| `role_id` | int | Conditionally | mutually exclusive with `user_id` | Any user with this role |
| `priority` | int | No | ≥0, default 0 | Ordering within the step |

**Source:** `workflow/schemas.py:44-64`, `workflow/schemas.py:29-41`, `workflow/schemas.py:21-26`.

### Response

`201 Created` — Returns `WorkflowDefinitionRead` (without steps):

```json
{
  "id": 1,
  "name": "Invoice Approval",
  "description": "Two-step invoice review process",
  "document_category_id": 1,
  "category_name": "Finance",
  "is_active": true,
  "created_by": 1,
  "created_at": "2026-08-09T10:00:00",
  "updated_at": "2026-08-09T10:00:00"
}
```

**Source:** `workflow/models.py:151-161`, `workflow/router.py:39-51`.

### Business Rules

1. **Name uniqueness:** `409 Conflict` if a workflow with the same name already exists. Checked against `workflow_definitions.name` (`service.py:146-153`).
2. **Category existence:** `404 Not Found` if `document_category_id` does not reference an existing category (`service.py:156-161`).
3. **Every step must have at least one approver:** `422 Unprocessable Entity` if any step has an empty `approvers` array (`service.py:41-43`).
4. **Exactly one of user_id or role_id per approver:** `422 Unprocessable Entity` if both or neither are set (`service.py:46-54`).
5. **Step order uniqueness:** Enforced by a database unique constraint on `(workflow_definition_id, step_order)` — migration `20260809_a1b2c3d4e5f7_workflow_definitions.py`.
6. **is_active defaults to `true`** on creation (`workflow/models.py:45`).
7. **created_by** is set to the authenticated user's ID (`service.py:168`).
8. The entire creation (definition + steps + approvers) is **atomic** — a single `session.commit()` (`service.py:193`).

### Database

**Tables written (in order):**

1. `workflow_definitions` — 1 row
2. `workflow_steps` — N rows (flushed individually to get auto-generated IDs)
3. `workflow_step_approvers` — M rows total

### Audit

| Field | Value |
|-------|-------|
| `action` | `CREATE_WORKFLOW` |
| `module` | `WORKFLOW` |
| `entity_name` | `"workflow_definition"` |
| `entity_id` | New definition's ID |
| `old_value` | `None` |
| `new_value` | `{"name": "...", "steps": N}` |
| `description` | `"Created workflow '...' with N step(s)"` |

**Source:** `audit/models.py:63`, `workflow/service.py:202-207`.

---

## 5. GET /api/v1/workflows/{definition_id}

### Purpose

Retrieve a single workflow definition with its complete step and approver details.

### Usage

Called by the admin UI when editing or viewing a workflow configuration. Unlike the list endpoint, this returns the full step tree with approver details including resolved user/role names.

### Access Control

- **Any authenticated user** (`CurrentUser` dependency, `workflow/router.py:60`).
- **RBAC middleware:** No entry for `GET /api/v1/workflows/` with a path suffix — the middleware allows it through.
- **Source:** `workflow/router.py:54-65`.

### Request

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `definition_id` | int | **Yes** | Path parameter — workflow definition ID |

### Response

`200 OK` — Returns `WorkflowDefinitionDetailRead`:

```json
{
  "id": 1,
  "name": "Invoice Approval",
  "description": "Two-step invoice review",
  "document_category_id": 1,
  "category_name": "Finance",
  "is_active": true,
  "created_by": 1,
  "created_at": "2026-08-09T10:00:00",
  "updated_at": "2026-08-09T10:00:00",
  "steps": [
    {
      "id": 1,
      "workflow_definition_id": 1,
      "step_order": 1,
      "step_name": "Manager Review",
      "approval_mode": "sequential",
      "is_active": true,
      "approvers": [
        {
          "id": 1,
          "workflow_step_id": 1,
          "user_id": 5,
          "role_id": null,
          "priority": 0,
          "is_active": true,
          "user_name": "John Smith",
          "role_name": null
        }
      ]
    }
  ]
}
```

**Source:** `workflow/models.py:164-165`, `workflow/service.py:211-234`.

### Business Rules

- Returns `404 Not Found` if `definition_id` does not exist (`service.py:57-63`).
- `user_name` and `role_name` in approvers are resolved from the `User` and `Role` relationships (`service.py:84-95`).
- Steps are returned in their stored order (no explicit sort — depends on DB default).

### How It Differs from GET /api/v1/workflows

| Aspect | List | Detail |
|--------|------|--------|
| Steps included | No | Yes, with approvers |
| Response model | `WorkflowDefinitionListResponse` | `WorkflowDefinitionDetailRead` |
| Filter params | Yes | No |
| Pagination | Yes | No |

### Database

- Tables read: `workflow_definitions`, `workflow_steps`, `workflow_step_approvers`, `users`, `roles`, `categories`
- All relationships use `selectin` eager loading.

### Audit

- No audit event. Read-only operation.

---

## 6. PUT /api/v1/workflows/{definition_id}

### Purpose

Update an existing workflow definition's metadata and/or replace its entire step/approver configuration.

### Usage

Called by an administrator when modifying an existing workflow. The PUT semantics mean: supplied scalar fields replace existing values; if `steps` is provided, it **completely replaces** all existing steps and approvers (not a merge).

### Access Control

- **Admin only** (`AdminUser` dependency, `workflow/router.py:76`).
- **RBAC middleware:** `("PUT", "/api/v1/workflows") → PermissionAction.UPDATE` (`middleware/rbac.py:39`).
- **Source:** `workflow/router.py:68-80`.

### Request

```json
{
  "name": "Updated Invoice Approval",
  "description": "Updated process",
  "document_category_id": 1,
  "is_active": true,
  "steps": [
    {
      "step_order": 1,
      "step_name": "New Step",
      "approval_mode": "parallel",
      "approvers": [
        { "user_id": 5, "priority": 0 },
        { "role_id": 2, "priority": 1 }
      ]
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | New name (must still be unique) |
| `description` | string | No | New description |
| `document_category_id` | int | No | Change category |
| `is_active` | bool | No | Change active state |
| `steps` | array | No | If provided, **replaces** all steps |

**Source:** `workflow/schemas.py:72-87`.

### Response

`200 OK` — Returns `WorkflowDefinitionRead` (without steps):

```json
{
  "id": 1,
  "name": "Updated Invoice Approval",
  ...
}
```

### Business Rules

1. **Omitted fields retain current values** — partial update for scalar fields (`service.py:288-314`).
2. **Name uniqueness:** If changing `name`, `409 Conflict` if another workflow has the same name (`service.py:290-298`).
3. **Category existence:** If changing `document_category_id`, `404 Not Found` if category doesn't exist (`service.py:304-310`).
4. **Step replacement is destructive:** When `steps` is provided, all existing steps and their approvers are deleted and recreated. There is no merge. (`service.py:317-345`).
5. **Step validation is re-applied** on the new steps (`service.py:318`).
6. The operation is atomic — single `session.commit()` (`service.py:348`).

### ⚠️ Design Decision: Effect on Running Instances

**Not yet specified in AGENTS.md.** The current implementation modifies the definition in place. If workflow instances (Phase 2) reference the definition, changing steps could affect pending approvals. This is a known design decision that requires confirmation:

- **Option A (current behavior):** Definition changes affect only future instances. Existing instances snapshot their steps at creation time.
- **Option B:** Deactivate the old definition and create a new one, preserving the old for existing instances.

**Recommendation:** Phase 2 (WorkflowInstanceService) should snapshot the definition at instance creation time, so definition changes do not corrupt running instances.

### Database

**Tables modified:**

- `workflow_definitions` — scalar fields updated
- `workflow_steps` — if `steps` provided: old rows deleted, new rows inserted
- `workflow_step_approvers` — if `steps` provided: old rows deleted, new rows inserted

### Audit

| Field | Value |
|-------|-------|
| `action` | `UPDATE_WORKFLOW` |
| `module` | `WORKFLOW` |
| `old_value` | `{"name": "...", "description": "...", "document_category_id": N, "is_active": bool}` |
| `new_value` | `{"name": "...", "description": "...", "document_category_id": N, "is_active": bool}` |

**Source:** `workflow/service.py:364-370`.

---

## 7. DELETE /api/v1/workflows/{definition_id}

### Purpose

Deactivate (soft-disable) a workflow definition by setting `is_active = false`.

### Usage

Called by an administrator to make a workflow unavailable for new document submissions without deleting it. The endpoint uses the HTTP DELETE verb, but the operation is a **logical state change**, not a physical database deletion.

### Access Control

- **Admin only** (`AdminUser` dependency, `workflow/router.py:92`).
- **RBAC middleware:** `("DELETE", "/api/v1/workflows") → PermissionAction.DELETE` (`middleware/rbac.py:40`).
- **Source:** `workflow/router.py:83-95`.

### Request

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `definition_id` | int | **Yes** | Path parameter |

No request body.

### Response

`200 OK` — Returns `WorkflowDefinitionRead` with `is_active: false`:

```json
{
  "id": 1,
  "name": "Invoice Approval",
  "is_active": false,
  ...
}
```

### Business Rules

1. **Soft-delete only:** Sets `is_active = false`, does **not** remove the row from the database (`service.py:378`).
2. **Returns 404** if the definition does not exist (`service.py:375`).
3. **Physical deletion is intentionally not supported.** The AGENTS.md spec states: *"Soft-delete via is_active = false — never hard-delete workflow definitions (referenced by instances in later phases)."*

### ⚠️ Design Decision: Effect on Running Instances

**Not yet specified in AGENTS.md.** Two behaviors are possible:

- **Option A:** Deactivating a definition does **not** affect already-running instances (they continue through their current approval chain). Only new submissions are blocked.
- **Option B:** Deactivating a definition cancels all pending instances.

**Recommendation:** Option A — deactivation is purely a "stop accepting new submissions" action. Running instances continue to completion.

### Database

- Table modified: `workflow_definitions` (`is_active` set to `false`, `updated_at` updated).

### Audit

| Field | Value |
|-------|-------|
| `action` | `DELETE_WORKFLOW` |
| `module` | `WORKFLOW` |
| `old_value` | `{"is_active": <previous_value>}` |
| `new_value` | `{"is_active": false}` |
| `description` | `"Deactivated workflow '...'"` |

**Source:** `workflow/service.py:383-389`.

---

## 8. PATCH /api/v1/workflows/{definition_id}/activate

### Purpose

Reactivate a previously deactivated workflow definition by setting `is_active = true`.

### Usage

Called by an administrator to make a previously deactivated workflow available again for new document submissions.

### Access Control

- **Admin only** (`AdminUser` dependency, `workflow/router.py:105`).
- **RBAC middleware:** No explicit entry for `PATCH /api/v1/workflows/` in `ROUTE_PERMISSION_MAP`. The middleware allows it through (no mapping → per-endpoint guard handles it). The `AdminUser` dependency enforces admin access.
- **Source:** `workflow/router.py:98-109`.

### Request

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `definition_id` | int | **Yes** | Path parameter |

No request body.

### Response

`200 OK` — Returns `WorkflowDefinitionRead` with `is_active: true`.

### Business Rules

1. **Sets `is_active = true`** (`service.py:398`).
2. **Returns 404** if the definition does not exist (`service.py:395`).
3. **No validation of steps/approvers** is performed before activation. A workflow with no steps could theoretically be activated. *(This is an implementation detail — a production system might want to validate that the workflow has at least one step with approvers before allowing activation. Not specified in AGENTS.md.)*
4. **Multiple active workflows per category** — the system allows multiple active workflows for the same document category. This is by design — different document types within a category may need different approval processes. *(Not explicitly specified in AGENTS.md.)*

### Database

- Table modified: `workflow_definitions` (`is_active` set to `true`, `updated_at` updated).

### Audit

| Field | Value |
|-------|-------|
| `action` | `ACTIVATE_WORKFLOW` |
| `module` | `WORKFLOW` |
| `old_value` | `{"is_active": <previous_value>}` |
| `new_value` | `{"is_active": true}` |
| `description` | `"Activated workflow '...'"` |

**Source:** `workflow/service.py:402-408`.

---

## 9. Workflow Definition Lifecycle

```
                    ┌─────────────────────┐
                    │   POST /workflows   │  Admin creates definition
                    │   (is_active=true)  │  with steps + approvers
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Active Definition  │  ← Available for document
                    │  is_active = true   │     submission (Phase 2)
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  PUT /{id}   │  │ DELETE /{id} │  │ PATCH /{id}  │
    │  Update      │  │ Deactivate   │  │ /activate    │
    └──────┬───────┘  └──────┬───────┘  │ (no-op if    │
           │                 │          │  already     │
           ▼                 ▼          │  active)     │
    ┌──────────────┐  ┌──────────────┐  └──────────────┘
    │   Updated    │  │  Inactive    │
    │  Definition  │  │ is_active =  │
    │ (still       │  │    false     │
    │  active)     │  └──────┬───────┘
    └──────────────┘         │
                             │  PATCH /{id}/activate
                             ▼
                    ┌──────────────┐
                    │    Active    │
                    │  (reactivated)
                    └──────────────┘
```

**Key invariants:**
- A definition is created with `is_active = true` by default.
- Deactivation (`DELETE`) sets `is_active = false` — the row remains.
- Activation (`PATCH /activate`) sets `is_active = true`.
- There is no "physical delete" endpoint — definitions are never removed from the database.

**Source:** Implemented across `workflow/service.py` methods `create_definition`, `update_definition`, `deactivate_definition`, `activate_definition`.

---

## 10. Workflow Definition vs Workflow Instance

| Aspect | Workflow Definition | Workflow Instance |
|--------|--------------------|--------------------|
| **What** | Reusable template | Single execution against a document |
| **Phase** | Phase 1 (implemented) | Phase 2 (not yet implemented) |
| **Tables** | `workflow_definitions`, `workflow_steps`, `workflow_step_approvers` | `workflow_instances`, `workflow_actions`, `workflow_history` |
| **Created by** | Admin (manual configuration) | User submitting a document for approval |
| **Lifecycle** | Persistent, can be activated/deactivated | Ephemeral: submitted → pending → approved/rejected/returned → archived |
| **Relationship** | Referenced by instances via `workflow_definition_id` | References a definition at creation time |

**How they relate (from AGENTS.md):**

```
workflow_definitions          workflow_instances
        │                            │
        ├──────────────►             │
        │               workflow_steps│
        │                    │       │
        │                    ▼       │
        │             workflow_step_ │
        │             approvers      │
        │                            │
        ▼                            ▼
   (template)              workflow_actions
                                   │
                                   ▼
                           workflow_history
```

**Why modifying a definition must not corrupt instances:**

AGENTS.md states: *"workflow_history is the approval-specific ledger; audit/ remains the system-wide event log."* This implies instances have their own immutable history. The recommended design (not yet implemented) is for Phase 2 to **snapshot the definition's steps at instance creation time**, so:
- Definition updates only affect future instances.
- Deactivating a definition does not cancel running instances.
- The workflow_history records the step configuration as it was when the instance was created.

**Source:** `AGENTS.md` under "Approval Workflow System — Database Tables" and "Workflow Status Enum".

---

## 11. Database Relationship

### Entity Relationship Diagram

```
categories
    │
    ▼ (1:N)
workflow_definitions ◄──────────── users (created_by)
    │
    ▼ (1:N)
workflow_steps
    │
    ├──────────────────► users (via workflow_step_approvers.user_id)
    │
    ├──────────────────► roles (via workflow_step_approvers.role_id)
    │
    ▼ (1:N)
workflow_step_approvers

workflow_definitions ◄──────────── workflow_instances (Phase 2)
                                         │
                                         ▼ (1:N)
                                    workflow_actions (Phase 2)
                                         │
                                         ▼ (1:N)
                                    workflow_history (Phase 2)
```

### Table Details

| Table | FK → Parent | Relationship |
|-------|-------------|--------------|
| `workflow_definitions` | `categories.id` | Each definition scopes to one category |
| `workflow_definitions` | `users.id` | `created_by` — the admin who created it |
| `workflow_steps` | `workflow_definitions.id` | Steps belong to one definition |
| `workflow_step_approvers` | `workflow_steps.id` | Approvers belong to one step |
| `workflow_step_approvers` | `users.id` | Optional — specific user approver |
| `workflow_step_approvers` | `roles.id` | Optional — role-based approver |

### Unique Constraints

- `workflow_definitions.name` — unique across all definitions
- `(workflow_steps.workflow_definition_id, workflow_steps.step_order)` — step order is unique within a definition

### Eager Loading

All relationships use `selectin` lazy loading, which means:
- Fetching a definition automatically loads its category, creator, and steps.
- Fetching a step automatically loads its approvers (and their user/role names).

**Source:** `workflow/models.py:56-65`, `workflow/models.py:85-92`, `workflow/models.py:112-121`.

---

## 12. RBAC Integration

### How Workflow Endpoints Map to Permission Verbs

The workflow definition APIs reuse the existing five permission verbs defined in `users/models.py:25-30` (`view`, `download`, `create`, `update`, `delete`). No new permission verbs are introduced, per AGENTS.md: *"Reuse existing role permission matrix — do not invent new permission verbs."*

| Endpoint | HTTP Method | RBAC Map Entry | Required Permission | Enforced By |
|----------|-------------|----------------|---------------------|-------------|
| `GET /workflows` | GET | None | Authentication only | `CurrentUser` |
| `POST /workflows` | POST | `("POST", "/api/v1/workflows") → CREATE` | `create` | `AdminUser` + RBAC |
| `GET /workflows/{id}` | GET | None | Authentication only | `CurrentUser` |
| `PUT /workflows/{id}` | PUT | `("PUT", "/api/v1/workflows") → UPDATE` | `update` | `AdminUser` + RBAC |
| `DELETE /workflows/{id}` | DELETE | `("DELETE", "/api/v1/workflows") → DELETE` | `delete` | `AdminUser` + RBAC |
| `PATCH /workflows/{id}/activate` | PATCH | None | Authentication only | `AdminUser` |

**Important notes:**

1. The `GET` endpoints have **no RBAC map entry**, so the middleware passes them through. `CurrentUser` ensures the caller is authenticated but does not check a specific permission verb. Any authenticated user can list and view workflow definitions.

2. The `PATCH /activate` endpoint has **no RBAC map entry** either. It is protected solely by the `AdminUser` dependency. This is a gap in the RBAC safety net — AGENTS.md states: *"New endpoints that require permission checks must be added here [ROUTE_PERMISSION_MAP], otherwise they are silently unprotected by the middleware."* However, since `AdminUser` already enforces admin-only access and admin bypasses RBAC anyway, this has no practical impact.

3. Admin users **always bypass** RBAC checks (`middleware/rbac.py:117-119`). The RBAC entries for POST/PUT/DELETE on `/api/v1/workflows` serve as a safety net for non-admin users who somehow reach those endpoints — but the `AdminUser` dependency already blocks them at the FastAPI layer.

### Role Permission Matrix

| Role | Can List/View | Can Create | Can Update | Can Deactivate | Can Activate |
|------|--------------|------------|------------|----------------|--------------|
| Admin | Yes | Yes | Yes | Yes | Yes |
| Maker | Yes | No | No | No | No |
| Checker | Yes | No | No | No | No |
| Auditor | Yes | No | No | No | No |

**Source:** `middleware/rbac.py:26-41`, `workflow/router.py` (AdminUser/CurrentUser dependencies).

---

## 13. Audit Integration

### Audit Mechanism

All write operations on workflow definitions use the centralized `AuditService.log_event()` method from `audit/service.py`. This is the same audit mechanism used by all other modules (auth, users, documents, categories, etc.). No separate workflow audit system is built.

**Source:** `workflow/service.py:110-132`.

### Audit Event Summary

| Operation | AuditAction | AuditModule | old_value | new_value |
|-----------|-------------|-------------|-----------|-----------|
| Create | `CREATE_WORKFLOW` | `WORKFLOW` | `None` | `{"name": "...", "steps": N}` |
| Update | `UPDATE_WORKFLOW` | `WORKFLOW` | Before state | After state |
| Deactivate | `DELETE_WORKFLOW` | `WORKFLOW` | `{"is_active": prev}` | `{"is_active": false}` |
| Activate | `ACTIVATE_WORKFLOW` | `WORKFLOW` | `{"is_active": prev}` | `{"is_active": true}` |

### Audit Fields Captured

Every audit event includes:
- `entity_name`: `"workflow_definition"`
- `entity_id`: The definition's integer ID (as string)
- `module`: `"workflow"` (from `AuditModule.WORKFLOW`)
- `description`: Human-readable text (e.g., "Created workflow 'Invoice Approval' with 2 step(s)")
- `is_success`: Always `true` (errors raise HTTP exceptions before reaching the audit call)

**Note:** Unlike the `audit/middleware.py` which captures IP, user-agent, and HTTP details, the workflow service calls `AuditService` directly without those fields. This is consistent with how other service-layer audit calls work (e.g., `categories/service.py:79-92`).

### Audit Log Immutability

Per AGENTS.md: *"Audit logs are immutable — no PUT/PATCH/DELETE endpoints exist for audit records."* Workflow audit events are written once and cannot be modified or deleted.

**Source:** `audit/models.py:62-66`, `workflow/service.py:202-207`, `workflow/service.py:364-370`, `workflow/service.py:383-389`, `workflow/service.py:402-408`.

---

## 14. API Comparison Matrix

| Method | Endpoint | Purpose | Access | Operation Type | Main Entity | Audit Action |
|--------|----------|---------|--------|----------------|-------------|--------------|
| `GET` | `/api/v1/workflows` | List definitions | Authenticated | Read | `workflow_definitions` | None |
| `POST` | `/api/v1/workflows` | Create definition | Admin | Create | `workflow_definitions` | `CREATE_WORKFLOW` |
| `GET` | `/api/v1/workflows/{id}` | Get definition detail | Authenticated | Read | `workflow_definitions` | None |
| `PUT` | `/api/v1/workflows/{id}` | Update definition | Admin | Update | `workflow_definitions` | `UPDATE_WORKFLOW` |
| `DELETE` | `/api/v1/workflows/{id}` | Deactivate definition | Admin | State change | `workflow_definitions` | `DELETE_WORKFLOW` |
| `PATCH` | `/api/v1/workflows/{id}/activate` | Activate definition | Admin | State change | `workflow_definitions` | `ACTIVATE_WORKFLOW` |

---

## 15. Endpoint Dependency Flow

### Happy Path (Create → Configure → Activate → Use)

```
GET /workflows                    — Verify no conflicts, list existing
        │
        ▼
POST /workflows                   — Create with steps + approvers
        │                          (is_active defaults to true)
        ▼
GET /workflows/{id}               — Verify creation, view details
        │
        ▼
PUT /workflows/{id}               — Fine-tune (optional)
        │
        ▼
[Workflow available for submission]  ← Phase 2: POST /workflow-instances
```

### Deactivation Path

```
Active Workflow (is_active=true)
        │
        ▼
DELETE /workflows/{id}            — Sets is_active=false
        │
        ▼
Inactive Workflow (is_active=false)
        │  — No new submissions can use it
        │  — Existing instances continue (Phase 2)
        │
        ▼
PATCH /workflows/{id}/activate    — Reactivate when needed
        │
        ▼
Active Workflow (is_active=true)
```

### Error Recovery Paths

```
POST /workflows → 409 Conflict (name exists)
        │
        ▼
Choose different name → POST /workflows again

POST /workflows → 422 (step missing approvers)
        │
        ▼
Add approver to step → POST /workflows again

PUT /workflows/{id} → 404 (definition not found)
        │
        ▼
Verify ID exists via GET /workflows first
```

---

## 16. Design Decisions / Items Requiring Confirmation

The following items are **not explicitly specified** in AGENTS.md and represent implementation decisions or gaps that should be confirmed before production use:

### 1. Effect of Definition Changes on Running Instances
**Status:** Not specified.
**Current behavior:** Definition is modified in place.
**Risk:** If Phase 2 instances reference the definition directly (not a snapshot), updating steps could corrupt running approvals.
**Recommendation:** Phase 2 should snapshot the definition at instance creation.

### 2. Effect of Deactivation on Running Instances
**Status:** Not specified.
**Current behavior:** Only `is_active` changes. No instance cancellation.
**Recommendation:** Deactivation should block new submissions only; existing instances continue.

### 3. Activation Validation
**Status:** Not specified.
**Current behavior:** No validation that the workflow has valid steps/approvers before activation.
**Risk:** An empty or invalid workflow could be activated.
**Recommendation:** Validate at least one step with approvers exists before activation.

### 4. Multiple Active Workflows per Category
**Status:** Not specified.
**Current behavior:** Multiple active workflows can coexist for the same category.
**Impact:** Phase 2 document submission UI must handle multiple valid workflows per category (dropdown selection).

### 5. RBAC Gap on PATCH /activate
**Status:** No `ROUTE_PERMISSION_MAP` entry for `PATCH /api/v1/workflows/`.
**Current behavior:** Protected by `AdminUser` dependency only.
**Impact:** No practical issue since admin bypasses RBAC. However, for defense-in-depth, an entry could be added.

### 6. Step Order Uniqueness Enforcement
**Status:** Defined by database constraint (`uq_workflow_step_order`).
**Current behavior:** Service validates; DB constraint is the safety net.
**Impact:** If two steps have the same `step_order`, the DB will reject the insert. The service does not pre-check this — the error message would be a raw DB integrity error, not a friendly 422.
**Recommendation:** Add explicit service-level validation for duplicate step orders.

### 7. Sorting of Steps in Detail Response
**Status:** Not specified.
**Current behavior:** Steps are returned in DB fetch order (no explicit `ORDER BY`).
**Recommendation:** Add `.order_by(WorkflowStep.step_order)` to the query for deterministic ordering.

---

*Documentation generated from source code: `workflow/router.py`, `workflow/service.py`, `workflow/models.py`, `workflow/schemas.py`, `middleware/rbac.py`, `audit/models.py`, and `AGENTS.md`.*
