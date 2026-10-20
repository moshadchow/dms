# DMS — SUPERADMIN Company Context for Cross-Company Data

Act as a **Senior Full-Stack Engineer, Security Architect, and Multi-Tenant Application Specialist** working on the existing DMS application.

Before making any changes:

1. Read `AGENTS.md` completely.
2. Inspect the existing backend and frontend implementation.
3. Identify the current implementation of:

   * SUPERADMIN
   * ADMIN
   * Company Profile
   * Workflow Definitions
   * Category-wise User Access
   * Categories
   * User Levels
   * RBAC
   * authenticated user/company context
   * existing dropdown/filter components
4. Reuse existing architecture and components wherever possible.
5. Do not introduce a second authorization or tenancy mechanism.

---

# 1. Target Authorization Model

The DMS has two different scopes.

## Global scope

The following remain GLOBAL across all companies:

```text
Roles
Permissions
Role → Permission assignments
User Levels
User Level definitions
```

These must NOT become company-specific.

---

## Company scope

The following business data is company-specific:

```text
Workflow Definitions
Category-wise User Access
```

Company A data must not be visible to Company B users.

---

# 2. SUPERADMIN Company Context

SUPERADMIN has system-wide visibility and therefore must be able to work with data belonging to **all companies**.

However, SUPERADMIN must always operate against an explicit **Company Context** when viewing company-specific data.

Add a reusable **Company Dropdown / Company Context selector** for SUPERADMIN.

Conceptually:

```text
SUPERADMIN
    |
    +-- Company Dropdown
          |
          +-- Company A
          +-- Company B
          +-- Company C
```

After selecting:

```text
Company A
```

company-specific screens must display:

```text
Company A workflows
Company A category-wise user access

```

After selecting:

```text
Company B
```

the same screens must display:

```text
Company B workflows
Company B category-wise user access
```

The selected company context must be applied server-side and must not be treated merely as a frontend display filter.

---

# 3. Company Dropdown Requirements

Inspect the existing Company Profile API and frontend implementation.

Reuse the existing company list API/component where practical.

The dropdown should:

* be visible to SUPERADMIN;
* contain active companies;
* display the appropriate company name/short name;
* have a clear selected state;
* support changing the company context;
* trigger reloading of the company-specific data;
* not alter global Roles, Permissions, or User Levels.

For normal ADMIN users:

```text
Company Context Dropdown
    = NOT REQUIRED
```

Their company context must continue to come automatically from:

```text
current_user.company_id
```

Do not allow an ADMIN to select another company.

---

# 4. SUPERADMIN Workflow Visibility

SUPERADMIN must be able to see **ALL Workflow Definitions across all companies**.

However, the workflow screen must require/select a Company Context.

Example:

```text
Company Context: [ Company A ▼ ]

Workflow List:
------------------------------
Workflow A1
Workflow A2
Workflow A3
```

Changing to:

```text
Company Context: [ Company B ▼ ]
```

must reload:

```text
Workflow B1
Workflow B2
```

SUPERADMIN must never need to modify API security by impersonating an ADMIN.

The authenticated user remains:

```text
SUPERADMIN
```

and the selected company is an explicit **management context**.

---

# 5. SUPERADMIN Must NOT Create Workflows

SUPERADMIN must NOT be able to create Workflow Definitions.

Remove/hide the:

```text
Create Workflow
```

button for SUPERADMIN.

This must be implemented in both layers:

### Frontend

The button must not be rendered for:

```text
SUPERADMIN
```

### Backend

The create workflow endpoint must reject SUPERADMIN requests even if the API is called directly.

Do NOT rely on hiding the button as a security mechanism.

Expected behavior:

```text
ADMIN
    → Create Workflow = ALLOWED

SUPERADMIN
    → Create Workflow = FORBIDDEN
```

The existing role/permission architecture must be respected.

Do not grant SUPERADMIN a workflow-create capability merely because the seed role currently contains generic `create` permission.

If necessary, introduce the minimum endpoint-specific authorization rule required to enforce this business restriction without changing the global permission model.

---

# 6. SUPERADMIN Workflow Operations

SUPERADMIN's workflow capabilities must be explicitly reviewed.

The requirement is:

```text
SUPERADMIN
    → View workflows across companies
    → Select company context
    → Cannot create workflows
```

Determine from the existing implementation whether SUPERADMIN should retain other existing workflow administration operations such as:

* view
* update
* activate
* deactivate

Do not infer or silently expand permissions.

Preserve existing business rules unless they conflict with the requirements in this specification.

For every allowed mutation, the selected Company Context must be validated server-side.

---

# 7. ADMIN Workflow Isolation

Normal ADMIN users remain strictly company-scoped.

```text
Company A ADMIN
    → Company A workflows only

Company B ADMIN
    → Company B workflows only
```

ADMIN must not be able to bypass company isolation through:

* query parameters;
* workflow IDs;
* API payloads;
* pagination;
* search;
* sorting;
* URL manipulation.

ADMIN does not receive a Company Dropdown.

The backend derives the company from:

```text
current_user.company_id
```

---

# 8. SUPERADMIN Category-wise User Access

Apply the same Company Context model to the **Category-wise User Access** functionality.

SUPERADMIN must be able to view category-wise user access for **all companies**, but must first select the company context.

Example:

```text
Company Context: [ Company A ▼ ]

Category-wise User Access
--------------------------------
Category       Users
Finance        User A, User B
HR             User C
Legal          User D
```

Changing the company:

```text
Company Context: [ Company B ▼ ]
```

must display only Company B's category-wise user access.

---

# 9. SUPERADMIN Cannot Modify Category-wise User Access

SUPERADMIN must NOT be allowed to create or modify Category-wise User Access.

Specifically remove/hide these buttons for SUPERADMIN:

```text
Save Permission
Clear All
```

The exact existing button labels/casing should be preserved or normalized according to the current UI implementation, but the functionality must be unavailable to SUPERADMIN.

Expected behavior:

```text
ADMIN
    → Category-wise access management = existing behavior

SUPERADMIN
    → View category-wise access = ALLOWED
    → Save Permission = FORBIDDEN
    → Clear All = FORBIDDEN
```

Again, frontend hiding is not sufficient.

The backend must reject unauthorized modification attempts from SUPERADMIN.

---

# 10. Category-wise Access Security

Inspect the existing Category-wise User Access implementation carefully.

Identify:

* router endpoints;
* service methods;
* request schemas;
* category/user relationships;
* existing permission checks;
* frontend API calls;
* Save Permission implementation;
* Clear All implementation.

Ensure SUPERADMIN's selected company context is used only for **reading/viewing** company-specific access data.

Do not allow a malicious SUPERADMIN API request to:

```text
POST/PUT/PATCH/DELETE
```

category access and bypass the UI restriction.

---

# 11. Company Context Must Be Server-Validated

Do not trust the frontend blindly.

If the frontend sends:

```text
company_id=123
```

the backend must validate:

1. the authenticated user is SUPERADMIN;
2. the company exists;
3. the company is active, where the existing business rules require active companies;
4. the requested company context is valid for the requested operation.

For normal ADMIN:

```text
requested_company_id
```

must NOT override:

```text
current_user.company_id
```

If an ADMIN attempts to manipulate the company context parameter, reject the request or ignore the parameter according to the safest existing API convention.

---

# 12. API Design

Inspect existing API conventions before adding parameters.

Prefer a clean and consistent approach such as:

```text
GET /api/v1/workflows?company_id=<id>
```

for SUPERADMIN viewing.

For ADMIN:

```text
GET /api/v1/workflows
```

must automatically scope to:

```text
current_user.company_id
```

Similarly, identify the existing Category-wise User Access endpoint and apply the same company-context strategy.

Do not create duplicate endpoints solely for SUPERADMIN unless the current architecture makes that necessary.

---

# 13. Prevent Company Context Leakage

Company context must never alter global entities.

Selecting:

```text
Company A
```

must NOT filter:

```text
Roles
Permissions
User Levels
```

because those remain global.

Only company-specific data should respond to the selected context:

```text
Workflow Definitions
Category-wise User Access
```

---

# 14. Frontend State Management

Inspect the existing authentication/Zustand/store architecture.

Do not create unnecessary global state if the existing workflow/category pages already have appropriate local state.

The Company Context should:

* initialize appropriately;
* load available companies;
* maintain the selected company;
* reload dependent data when the selection changes;
* clear stale company-specific records when switching companies;
* prevent displaying Company A data after Company B has been selected;
* handle loading and error states cleanly.

Avoid race conditions when rapidly changing the company selection.

---

# 15. UX Requirements

The Company Dropdown should be placed in a logical, reusable location on the relevant SUPERADMIN pages.

Use the existing DMS design system and components.

Do not introduce a visually inconsistent component.

For SUPERADMIN workflow screen:

```text
Company Profile: [ Select Company ▼ ]

[Workflow list]
```

Do NOT display:

```text
Create Workflow
```

For SUPERADMIN category-wise access screen:

```text
Company Profile: [ Select Company ▼ ]

[Category-wise access list]
```

Do NOT display:

```text
Save Permission
Clear All
```

When no company is selected, do not accidentally load all company-specific records.

Prefer a clear state such as:

```text
Please select a company.
```

until a company context is established.

---

# 16. Backend Authorization Matrix

Implement and verify the following:

| Function                            | ADMIN                  | SUPERADMIN                                |
| ----------------------------------- | ---------------------- | ----------------------------------------- |
| View own-company workflows          | ALLOW                  | ALLOW                                     |
| View workflows from other companies | DENY                   | ALLOW with Company Context                |
| Create workflow                     | ALLOW                  | DENY                                      |
| Modify workflow                     | Existing rules         | Existing rules + selected company context |
| View category-wise access           | Existing company scope | ALLOW with Company Context                |
| Save category-wise permission       | Existing rules         | DENY                                      |
| Clear category-wise permissions     | Existing rules         | DENY                                      |
| Roles                               | Global                 | Global                                    |
| Permissions                         | Global                 | Global                                    |
| User Levels                         | Global                 | Global                                    |

Do not change unrelated roles unless required by the existing implementation.

---

# 17. Database

Do not introduce company IDs into:

```text
roles
permissions
user_levels
```

unless the existing schema already requires them.

Workflow Definitions must remain company-scoped.

Category-wise User Access must use the existing company relationship/data model.

Do not create duplicate company relationships.

Inspect existing migrations before adding anything.

If a migration is required, create an Alembic migration following the project's existing conventions.

---

# 18. Audit Trail

Use the existing:

```text
AuditService.log_event()
```

for applicable operations.

Do not introduce another audit mechanism.

If viewing company-specific administrative data is already audited by the existing system, preserve that behavior.

If company context is included in audit metadata, ensure the selected company is recorded accurately.

---

# 19. Testing

Use the existing SQLite + StaticPool test architecture.

Add backend tests for:

### Workflow

1. Company A ADMIN sees only Company A workflows.
2. Company B ADMIN sees only Company B workflows.
3. SUPERADMIN can view Company A workflows with Company A context.
4. SUPERADMIN can view Company B workflows with Company B context.
5. SUPERADMIN cannot create a workflow.
6. Direct API request attempting SUPERADMIN workflow creation returns 403.
7. ADMIN cannot use `company_id` to access another company's workflows.
8. SUPERADMIN changing company context returns the correct dataset.
9. No company selected does not return all workflows accidentally.
10. Search/pagination/sorting remain within the selected company context.

### Category-wise User Access

11. SUPERADMIN can view Company A category access.
12. SUPERADMIN can view Company B category access.
13. SUPERADMIN cannot save permissions.
14. SUPERADMIN cannot clear all permissions.
15. Direct API attempts to modify category access as SUPERADMIN return 403.
16. ADMIN behavior remains unchanged and company-scoped.
17. Switching company context cannot display stale records from the previous company.

### Global Entities

18. Roles remain global.
19. Permissions remain global.
20. User Levels remain global.
21. Existing RBAC tests continue passing.

---

# 20. Frontend Tests / Verification

Verify SUPERADMIN UI behavior:

### Workflow page

```text
SUPERADMIN
    ✓ Company Dropdown visible
    ✓ Company list available
    ✓ Company A selection loads Company A workflows
    ✓ Company B selection loads Company B workflows
    ✗ Create Workflow button
```

### Category-wise User Access page

```text
SUPERADMIN
    ✓ Company Dropdown visible
    ✓ Company A selection loads Company A access
    ✓ Company B selection loads Company B access
    ✗ Save Permission
    ✗ Clear All
```

### ADMIN

```text
ADMIN
    ✗ Company Dropdown
    ✓ Existing company-scoped workflow behavior
    ✓ Existing category-access behavior
```

---

# 21. Regression Verification

Run:

```bash
alembic upgrade head
pytest
```

Then:

```bash
cd dms-app
npm run build
npm run lint
```

Do not consider the implementation complete if existing tests fail.

If an existing test encodes behavior that conflicts with this new requirement, update the test only after confirming that the changed behavior is intentional.

---

# 22. Security Acceptance Criteria

The following must be true after implementation:

```text
GLOBAL
────────────────────────────
Roles
Permissions
User Levels


COMPANY-SCOPED
────────────────────────────
Workflow Definitions
Category-wise User Access
```

For SUPERADMIN:

```text
SUPERADMIN
    ↓
Select Company Context
    ↓
View selected company's workflows/access
```

But:

```text
SUPERADMIN
    ✗ Create Workflow
    ✗ Save Permission
    ✗ Clear All
```

For ADMIN:

```text
ADMIN
    ↓
Automatically scoped to current_user.company_id
    ↓
Cannot select another company
```

No client-side manipulation, query parameter, ID substitution, or direct API call may bypass these rules.

---

# 23. Implementation Discipline

Before coding:

* inspect existing implementation;
* identify reusable Company Dropdown/API;
* identify current role checks;
* identify exact workflow create endpoint;
* identify exact category permission save/clear endpoints;
* identify current SUPERADMIN frontend checks;
* identify current company-scoping logic.

Then implement the **minimum production-safe changes**.

Do not rewrite working modules.

Do not duplicate authorization logic unnecessarily.

Do not introduce a new RBAC framework.

Do not introduce a new multi-tenancy framework.

Do not make Roles, Permissions, or User Levels company-specific.

---

# 24. Final Deliverable

After implementation, provide:

1. Files changed.
2. API changes.
3. Database/migration changes, if any.
4. SUPERADMIN company-context implementation.
5. Workflow authorization changes.
6. Category-wise access authorization changes.
7. Frontend UI changes.
8. Tests added/updated.
9. Backend test result.
10. Frontend build/lint result.
11. Any data migration considerations.
12. Any remaining risks or follow-up items.

Do not claim successful execution unless the actual repository was modified and the verification commands were executed successfully.
