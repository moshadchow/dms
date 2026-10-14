# DMS — Global Roles/Permissions with Company-Specific Workflow Definitions

Act as a **Senior Full-Stack Engineer and Security Architect** working on the existing DMS application.

Before making any changes, **read `AGENTS.md` completely** and inspect the existing implementation. Do not redesign working functionality unnecessarily. Extend the existing architecture and conventions.

## Objective

Implement and enforce the following multi-company authorization model:

### 1. Global Security Configuration

The following entities are **global across the entire DMS system** and must NOT be company-scoped:

* Roles
* User Levels
* Permissions
* Role → Permission assignments
* User Level definitions

A role, permission, or user level created/configured for one company must be available system-wide.

For example:

```text
Company A
Company B
Company C
     |
     +---- Shared Roles
     +---- Shared Permissions
     +---- Shared User Levels
```

Do **not** add `company_id` to Roles, Permissions, or User Levels unless the existing schema proves that it is already required for another valid reason.

The existing RBAC permission model must remain unchanged and continue using:

```text
view
download
create
update
delete
```

Do not introduce new permission verbs.

The existing RBAC middleware and permission dependencies remain the source of truth for authorization. `AdminUser`, `SuperAdminUser`, `CurrentUser`, `require_permission()`, and `ROUTE_PERMISSION_MAP` must continue to be used according to the existing architecture.

---

# 2. Company-Specific Workflow Definitions

`WorkflowDefinition` is different from Roles, Permissions, and User Levels.

Every Workflow Definition must be **company-specific**.

A workflow definition must belong to exactly one company through the appropriate company relationship.

Conceptually:

```text
Company A
   ├── Workflow A1
   ├── Workflow A2
   └── Workflow A3

Company B
   ├── Workflow B1
   └── Workflow B2
```

Company A users must never be able to see, retrieve, modify, activate, deactivate, or otherwise access Company B workflow definitions.

Likewise, Company B users must never be able to access Company A workflow definitions.

This isolation must be enforced **server-side**, not merely by hiding records in the React UI.

---

# 3. Identify the Correct Company Context

Before implementation, inspect:

* `company_profile/models.py`
* `company_profile/service.py`
* `users/models.py`
* `users/service.py`
* `core/dependencies.py`
* `workflow/` models
* `workflow/definition_service.py`
* `workflow/instance_service.py`
* `workflow/approval_service.py`
* `workflow/approval_policy.py`
* `workflow/router.py`
* existing migrations
* existing workflow tests
* frontend workflow API/services/pages/components

Determine the existing canonical relationship:

```text
users.company_id → companies.id
```

Use that existing relationship rather than creating another company-identification mechanism.

The authenticated user's company must be obtained from the authenticated user context.

Never trust a client-supplied company ID to determine the user's security scope.

---

# 4. Workflow Definition Data Model

Inspect the existing `WorkflowDefinition` model first.

If `WorkflowDefinition` does not already have a company relationship, add the minimum required field:

```text
company_id
```

with a proper foreign key to the existing companies table.

Follow the project's existing SQLModel conventions.

The relationship should allow the workflow definition's company to be loaded efficiently.

Do not duplicate company information inside workflow records.

Do not create a separate tenant/company table.

Do not alter the existing `document_category_id` design decision. Workflow definitions remain category-agnostic; category filtering continues to happen at the document level.

---

# 5. Workflow Definition Creation

When an ADMIN creates a Workflow Definition:

```text
authenticated_admin.company_id
            ↓
WorkflowDefinition.company_id
```

The company must be assigned **server-side**.

The frontend must not be able to choose another company.

If the request contains a `company_id` supplied by the client:

* ignore it, or
* reject it with a validation/authorization error,

depending on the existing API design.

Never allow:

```text
Company A ADMIN
      ↓
POST workflow
company_id = Company B
```

to create a Company B workflow.

If the authenticated ADMIN has no company assignment, do not create an unscoped workflow. Return an appropriate authorization/business error consistent with the existing API behavior.

---

# 6. SUPERADMIN Workflow Behavior

Inspect the existing SUPERADMIN design before implementation.

SUPERADMIN is the system-level administrator and retains existing system-wide administrative capabilities.

However, do not automatically assume that SUPERADMIN should bypass company isolation for normal workflow operations.

Implement the workflow visibility/access rules based on the existing authorization architecture and the intended business semantics.

At minimum:

* SUPERADMIN-created/configured workflows must have an explicit company context.
* Do not create company-less Workflow Definitions unless the existing architecture explicitly requires global workflows.
* SUPERADMIN must not accidentally create a workflow that becomes visible to every company.

If the existing UI/API allows SUPERADMIN to manage workflows across companies, ensure that company selection is explicit and validated against active companies.

---

# 7. Workflow Definition List

Modify `WorkflowDefinitionService` list/query behavior so that company isolation is enforced at the database query level.

For a normal company-bound user:

```text
WHERE workflow_definitions.company_id = current_user.company_id
```

Do not retrieve all workflow definitions and filter them afterward.

Filtering must happen before:

* search
* sorting
* pagination
* total-count calculation

Therefore:

```text
Company A ADMIN
    ↓
Database query
    ↓
Company A workflows only
    ↓
search/sort/pagination
    ↓
response
```

Never:

```text
Database query → all workflows
                    ↓
              frontend filtering
```

---

# 8. Workflow Definition Detail

For endpoints such as:

```text
GET /api/v1/workflows/{id}
```

enforce company ownership server-side.

A Company A user requesting a Company B workflow ID must receive an appropriate response, preferably:

```text
404 Not Found
```

when consistent with the application's existing resource-isolation pattern.

Do not expose:

* workflow name
* workflow steps
* approvers
* approval mode
* company information
* internal IDs
* configuration details

for another company's workflow.

---

# 9. Update / Activate / Deactivate / Delete

Apply the same company isolation to every Workflow Definition mutation.

Before performing:

* update
* activate
* deactivate
* delete

verify that the target Workflow Definition belongs to the authenticated user's company.

A Company A administrator must never be able to modify:

```text
Company B workflow
```

by manipulating the workflow ID.

Do not rely solely on frontend route guards.

---

# 10. Workflow Steps and Approvers

Inspect the existing relationships:

```text
WorkflowDefinition
    ↓
WorkflowStep
    ↓
WorkflowStepApprover
    ↓
User
```

Ensure that company isolation cannot be bypassed through nested workflow operations.

For example, a Company A administrator must not be able to:

* attach Company B users as workflow approvers,
* modify Company B workflow steps,
* add Company B users to Company A workflows through ID manipulation,
* use another company's workflow definition ID while creating/updating workflow configuration.

Approver eligibility must continue to respect the existing RBAC and User Level rules.

The existing architecture explicitly requires approver eligibility to be enforced through `workflow_step_approvers` on top of RBAC.

---

# 11. User-Level Integration

Do NOT make User Levels company-specific.

User Levels remain globally defined.

However, existing document visibility rules must continue to apply.

Do not weaken:

```text
User Level access
+
RBAC permission
+
Workflow approver eligibility
+
Company isolation
```

These are separate authorization dimensions.

The existing workflow behavior states that an approver who cannot view the underlying document because of User Level restrictions must not become a valid approver merely because they are part of a workflow. Preserve this behavior.

---

# 12. Workflow Instances

Carefully distinguish:

### Workflow Definition

Company-specific configuration/template:

```text
WorkflowDefinition.company_id
```

### Workflow Instance

An execution of a workflow against a document.

Inspect the existing document/company relationship and determine the safest way to ensure that a workflow instance cannot cross company boundaries.

A Company A document must not start or execute a workflow definition belonging to Company B.

At workflow submission time, validate:

```text
document.company
        ==
workflow_definition.company
```

where the existing document model provides a company relationship directly or indirectly.

Do not allow a client to bypass this by submitting arbitrary workflow/document IDs.

The existing snapshot behavior must remain intact: once a workflow instance is created, its workflow steps are snapshotted, and subsequent definition changes must not alter the running instance.

---

# 13. Frontend Requirements

Inspect the existing workflow frontend before changing it.

The frontend should reflect the company-scoped behavior naturally through the API.

Do not implement security by frontend filtering.

The UI should:

* display only workflows returned for the authenticated user's company;
* never populate another company's workflows;
* not expose company selection to normal ADMIN users;
* use the existing `apiClient` from `dms-app/src/api/client.ts`;
* preserve existing loading, pagination, search, sorting, and error handling.

The API client convention must remain:

```text
apiClient.get('/workflows')
```

with the existing `/api/v1` base URL.

---

# 14. API Security

Review every Workflow Definition endpoint in `workflow/router.py`.

Confirm that company isolation applies consistently to:

* list
* create
* detail
* update
* activate
* deactivate/delete

Review `middleware/rbac.py`.

Ensure workflow endpoints continue to have the correct entries in:

```text
ROUTE_PERMISSION_MAP
```

The existing project specifically requires new/protected workflow endpoints to be represented in this map because missing entries can bypass the middleware safety net.

Do not create a second authorization middleware.

---

# 15. Audit Trail

Use the existing centralized:

```text
AuditService.log_event()
```

Do not introduce another audit mechanism.

Workflow create/update/activate/deactivate/delete operations must continue to generate the appropriate audit events.

Where useful, ensure audit metadata identifies the company/workflow context without exposing another company's data to unauthorized users.

The existing architecture explicitly requires `AuditService` as the centralized audit mechanism.

---

# 16. Database Migration

If `WorkflowDefinition.company_id` is missing:

1. Create an Alembic migration.
2. Add the FK to the existing companies table.
3. Determine how existing workflow definitions should be migrated.
4. Do not silently assign existing workflows to an arbitrary company.
5. If existing records cannot be safely mapped, identify them explicitly and handle migration safely.

Before writing the migration, inspect:

* current workflow records
* existing company records
* seed data
* migration history
* foreign-key conventions

The migration must be production-safe and reversible where practical.

---

# 17. Test Coverage

Add/update backend tests using the existing SQLite + StaticPool test architecture.

Do not switch tests to PostgreSQL.

The existing test fixture patches:

```text
core.database.engine
middleware.rbac.engine
middleware.audit.engine
```

Preserve that architecture.

Create test coverage for at least:

### Global Configuration

1. Role is visible/usable across Company A and Company B.
2. Permissions remain global.
3. User Levels remain global.
4. Existing RBAC behavior remains unchanged.

### Workflow Isolation

5. Company A ADMIN sees Company A workflows.
6. Company A ADMIN does not see Company B workflows.
7. Company B ADMIN sees Company B workflows.
8. Company B ADMIN does not see Company A workflows.
9. Company A ADMIN cannot retrieve Company B workflow by ID.
10. Company A ADMIN cannot update Company B workflow.
11. Company A ADMIN cannot activate Company B workflow.
12. Company A ADMIN cannot deactivate/delete Company B workflow.
13. Search cannot reveal another company's workflow.
14. Pagination cannot reveal another company's workflow.
15. Sorting cannot reveal another company's workflow.
16. Query parameters cannot override company scope.
17. Client-supplied `company_id` cannot create a workflow for another company.
18. Company A workflow cannot be attached to a Company B document.
19. Company B users cannot be added as approvers to a Company A workflow unless the existing business rules explicitly permit it.
20. Existing User Level restrictions remain enforced.

### Regression

21. Existing workflow tests continue to pass.
22. Existing RBAC tests continue to pass.
23. Existing user/company tests continue to pass.
24. Existing document/workflow instance tests continue to pass.

---

# 18. Security Acceptance Criteria

The implementation is considered complete only when these invariants are true:

```text
Roles
    = GLOBAL

Permissions
    = GLOBAL

User Levels
    = GLOBAL

Workflow Definitions
    = COMPANY-SCOPED

Workflow Instances
    = MUST NOT CROSS COMPANY BOUNDARIES
```

And:

```text
Company A ADMIN
    → Company A workflows only

Company B ADMIN
    → Company B workflows only
```

No frontend manipulation, query parameter, workflow ID, document ID, or nested resource ID may bypass these restrictions.

---

# 19. Performance Requirements

Do not introduce N+1 queries.

Use appropriate SQL joins/selectin loading consistent with the existing implementation.

Company filtering must be performed in SQL.

For workflow list endpoints, ensure that:

* filtered count is calculated correctly;
* pagination operates on the filtered dataset;
* search operates only within the user's company;
* indexes are considered for `workflow_definitions.company_id`.

---

# 20. Do Not Break Existing Architecture

Do NOT:

* create a new RBAC system;
* create company-specific Roles;
* create company-specific Permissions;
* create company-specific User Levels;
* duplicate the Company model;
* rely on frontend-only filtering;
* trust client-supplied company IDs for authorization;
* expose cross-company workflow data;
* modify unrelated modules unnecessarily;
* change existing workflow lifecycle semantics;
* remove existing User Level restrictions;
* introduce a second audit mechanism.

Prefer the smallest production-safe change that satisfies the requirements.

---

# 21. Verification

After implementation:

### Backend

Run:

```bash
alembic upgrade head
pytest
```

### Frontend

Run:

```bash
cd dms-app
npm run build
npm run lint
```

Also inspect the generated API behavior manually or through tests for:

```text
Company A ADMIN → only Company A workflows
Company B ADMIN → only Company B workflows
```

Test direct API access using workflow IDs belonging to the other company.

Confirm those requests cannot retrieve or modify cross-company workflows.

Finally, review the git diff and ensure that no unrelated files or functionality were changed.

Provide a concise implementation summary containing:

1. Files changed
2. Database migration added
3. Company-isolation approach
4. Global-vs-company-scoped behavior
5. Security controls added
6. Tests added/updated
7. Test/build/lint results
8. Any migration/data considerations
