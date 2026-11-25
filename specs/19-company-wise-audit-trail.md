# DMS — Implement Company-Wise Audit Trail Filtering

Act as a **Senior Full-Stack Engineer, Security Architect, and Multi-Tenant Application Specialist** working on the existing DMS application.

## Objective

Implement **company-wise filtering for the Audit Trail** in the Admin Panel.

The current Audit Trail must be enhanced so that:

```text
ADMIN Company A
    → sees only Company A audit records

ADMIN Company B
    → sees only Company B audit records

SUPERADMIN
    → can view audit records for any company
    → must select a Company Context
```

The implementation must be secure at the **database/API layer**, not merely filtered in React.

---

# 1. Read and Inspect First

Before changing anything:

1. Read `AGENTS.md` completely.
2. Inspect the existing Audit Trail implementation.
3. Inspect:

   * `audit/models.py`
   * `audit/service.py`
   * `audit/router.py`
   * audit schemas
   * audit database queries
   * `middleware/audit.py`
   * `users/models.py`
   * `company_profile/`
   * `core/dependencies.py`
   * RBAC middleware
   * Admin Panel Audit Trail UI
   * Audit API/service files
   * existing Company Dropdown implementation
   * existing SUPERADMIN Company Context implementation in Workflows and Category Access
   * audit-related tests
   * migrations

Do not assume filenames. Locate the actual implementation.

---

# 2. Existing Audit Architecture Must Be Preserved

The project already has a centralized:

```text
AuditService.log_event()
```

Use this existing service.

Do NOT:

* create another audit logger;
* create a second audit table;
* duplicate audit-writing logic;
* bypass the existing audit service;
* change the existing audit immutability model.

All existing audit-writing functionality must continue working.

---

# 3. Critical Multi-Company Requirement

Audit records must be associated with the company in which the audited activity occurred.

The filtering model must be:

```text
Audit Record
      ↓
Company Context
      ↓
Company
```

The implementation must determine the safest existing relationship for deriving the company.

For example, inspect whether an audit event can determine company through:

```text
Audit Event
    ↓
User
    ↓
User.company_id
```

or whether some events are better associated through another business entity.

Do not blindly assume that every audit event can be scoped only through the logged-in user.

---

# 4. Audit Company Attribution

This is a critical requirement.

When an audit event is created, determine its company correctly.

For example:

```text
Company A ADMIN
    ↓
Uploads document
    ↓
Audit event
    ↓
Company A
```

and:

```text
Company B ADMIN
    ↓
Updates document
    ↓
Audit event
    ↓
Company B
```

The stored audit record must allow the Audit Trail API to efficiently filter by company.

Inspect the existing `audit` table/model before making schema changes.

If a direct `company_id` does not currently exist and cannot be reliably derived at query time, add:

```text
company_id
```

to the audit record using the existing `companies` table.

Use the minimum schema change necessary.

---

# 5. Important: Do Not Misclassify SUPERADMIN Events

SUPERADMIN is a cross-company administrative user.

Therefore, do NOT blindly assign every SUPERADMIN audit event to:

```text
SUPERADMIN.company_id
```

especially if SUPERADMIN has no company assignment.

For company-specific actions performed by SUPERADMIN, the audit event must identify the **selected/target company context**, where applicable.

Example:

```text
SUPERADMIN
    ↓
Company Context = Company A
    ↓
Views/manages Company A audit-related data
    ↓
Company context = Company A
```

The implementation must inspect the existing SUPERADMIN/company-context design and preserve a clear distinction between:

```text
actor
```

and:

```text
target company/context
```

Do not incorrectly classify a cross-company SUPERADMIN action as belonging to a nonexistent personal company.

---

# 6. ADMIN Audit Trail Filtering

For a normal ADMIN:

```text
current_user.company_id
```

must be the authoritative scope.

Example:

```text
Company A ADMIN
    ↓
GET /api/v1/audit-logs
    ↓
WHERE audit.company_id = current_user.company_id
```

The ADMIN must see **only Company A records**.

Company B records must never appear.

This must apply to:

* normal list;
* search;
* pagination;
* sorting;
* date filtering;
* event filtering;
* user filtering;
* exported records, if export exists;
* audit detail lookup.

---

# 7. ADMIN Must Not Override Company Scope

If the Audit API currently accepts:

```text
company_id
```

do NOT allow an ADMIN to use it to access another company.

For example:

```text
Company A ADMIN
GET /audit-logs?company_id=Company-B
```

must still return only Company A data or reject the request according to the existing API security convention.

Never allow:

```text
client company_id
```

to override:

```text
current_user.company_id
```

for ADMIN users.

---

# 8. SUPERADMIN Company Dropdown

Add/use the existing **Company Dropdown / Company Context selector** for SUPERADMIN in:

```text
Admin Panel → Audit Trail
```

The UI should display:

```text
Company Profile: [ Select Company ▼ ]
```

The dropdown must:

* be visible to SUPERADMIN;
* contain active companies;
* use the existing Company Profile/company-list API;
* display the correct company name/short name;
* not remain blank;
* use the existing company-selection pattern already implemented in Workflows/Category Access.

Do not create a duplicate company-loading mechanism if an existing reusable component/hook exists.

---

# 9. SUPERADMIN Must Explicitly Select Company

When no company is selected:

```text
selectedCompanyId = null
```

do NOT return all Audit Trail records.

Instead display an appropriate state such as:

```text
Please select a company.
```

The frontend must not accidentally issue:

```text
GET /audit-logs
```

without a company context if that would cause an all-company response.

---

# 10. SUPERADMIN — Company A

When SUPERADMIN selects:

```text
Company A
```

the Audit Trail API must return:

```text
Company A audit records ONLY
```

For example:

```text
Company Profile: [ Company A ▼ ]

Audit Trail
------------------------------------------------
User       Activity              Date
Admin A    Login                 ...
Admin A    Upload Document       ...
Admin A    Update Document       ...
```

No Company B or Company C records may appear.

---

# 11. SUPERADMIN — Company B

When SUPERADMIN changes:

```text
Company A
```

to:

```text
Company B
```

the UI must:

1. clear/replace the previous Company A audit data;
2. trigger a new API request;
3. pass Company B context;
4. display only Company B records.

Expected behavior:

```text
Company A selected
      ↓
Company A audit records

Change to Company B
      ↓
Clear/replace Company A state
      ↓
Fetch Company B
      ↓
Company B audit records only
```

Company A records must not remain visible after Company B is selected.

---

# 12. Prevent Stale Data and Race Conditions

Handle rapid company changes safely.

Example:

```text
Request A → Company A
Request B → Company B
```

If Request A completes after Request B, its response must not overwrite the Company B state.

Use the existing frontend architecture to ensure that the latest selected company controls the displayed data.

---

# 13. Audit API

Inspect the existing:

```text
GET /api/v1/audit-logs
```

endpoint.

Extend the current API rather than creating an unnecessary second Audit Trail endpoint.

For example, if consistent with the existing architecture:

```text
GET /api/v1/audit-logs?company_id=<id>
```

For SUPERADMIN:

```text
company_id
    = selected company context
```

For ADMIN:

```text
company_id
    = current_user.company_id
```

The exact endpoint/query parameter should follow the existing implementation if a different convention is already established.

---

# 14. Database-Level Filtering

Filtering MUST occur in the database query.

Do NOT:

```text
SELECT all audit records
        ↓
Python filtering
        ↓
React filtering
```

Instead:

```text
SELECT audit records
WHERE company_id = selected_company_id
```

Apply company filtering before:

* search;
* sort;
* pagination;
* count;
* export.

This is both a security and performance requirement.

---

# 15. Audit Detail Endpoint

Inspect:

```text
GET /api/v1/audit-logs/{id}
```

A Company A ADMIN must not be able to obtain a Company B audit record by guessing/manipulating its ID.

For example:

```text
Company A ADMIN
    ↓
GET /audit-logs/Company-B-record-id
    ↓
DENY
```

Prefer the existing resource-isolation response convention, typically `404 Not Found`, if consistent with the application.

SUPERADMIN may access records belonging to the selected company context.

---

# 16. Audit Export

The existing Audit Trail module supports CSV export.

Apply exactly the same company-scoping rules to:

```text
GET /api/v1/audit-logs/export
```

### ADMIN

Export:

```text
own company's audit records only
```

### SUPERADMIN

Export:

```text
selected company's audit records only
```

Never allow SUPERADMIN to accidentally export all companies when a company context is required.

Never allow ADMIN to export another company's records through query manipulation.

---

# 17. Search and Filtering

If the Audit Trail supports:

* username;
* event type;
* action;
* date range;
* resource;
* search;
* pagination;

the company filter must always remain active.

Example:

```text
Company A
+
Search = "document"
+
Date = September 2026
```

must search only:

```text
Company A audit records
```

It must never search the entire audit table first and filter afterward.

---

# 18. Company Attribution for Existing Audit Records

Inspect existing audit records.

Determine whether historical audit events already contain enough information to determine their company.

Possible strategies:

### Preferred

If company can be reliably derived from an existing relationship, use that relationship.

### If direct company_id is required

Create an Alembic migration and safely backfill:

```text
audit.company_id
```

from the authoritative existing relationship.

Do NOT assign historical records to an arbitrary company.

Identify records where company attribution cannot be safely determined.

Handle those explicitly rather than guessing.

---

# 19. Audit Events Without a User

Inspect whether the system creates audit events where:

```text
user_id = NULL
```

For system-generated events, determine the correct company attribution from the affected business entity.

For example:

```text
Document event
    ↓
Document company
```

or:

```text
Workflow event
    ↓
WorkflowDefinition.company_id
```

Do not automatically assign system events to a user's company when no user exists.

The company attribution must represent the actual business context of the event.

---

# 20. Frontend API State

Inspect the existing Audit Trail React component/service.

Ensure the request dependency includes:

```text
selectedCompanyId
```

Conceptually:

```text
selectedCompanyId
        ↓
fetchAuditLogs()
        ↓
API
```

When the selected company changes:

```text
setAuditLogs([])
setLoading(true)
fetchAuditLogs(newCompanyId)
```

Use the project's existing state-management conventions.

---

# 21. Company Dropdown Consistency

Compare:

```text
Admin Panel → Workflows
Admin Panel → Category Access
Admin Panel → Audit Trail
```

The SUPERADMIN Company Dropdown should behave consistently across all three.

Verify:

* same company source;
* same ID;
* same display field;
* same active-company filtering;
* same selection behavior;
* same loading/error handling.

If a reusable Company Context component already exists, use it.

Avoid three separate implementations that can drift apart.

---

# 22. Security Matrix

Implement and verify:

| Function                             | ADMIN            | SUPERADMIN                 |
| ------------------------------------ | ---------------- | -------------------------- |
| View audit records                   | Own company only | Selected company           |
| View another company's audit         | DENY             | ALLOW with Company Context |
| Search                               | Own company only | Selected company           |
| Pagination                           | Own company only | Selected company           |
| Detail                               | Own company only | Selected company           |
| Export                               | Own company only | Selected company           |
| Change company                       | DENY             | ALLOW                      |
| No company selected                  | N/A              | No company-specific data   |
| Override company via query parameter | DENY             | Validated                  |

---

# 23. Tests — Backend

Add regression tests for:

### ADMIN Company Isolation

1. Company A ADMIN sees Company A audit records.
2. Company A ADMIN does not see Company B records.
3. Company B ADMIN sees Company B records.
4. Company B ADMIN does not see Company A records.
5. ADMIN cannot override company using `company_id`.
6. ADMIN cannot retrieve another company's audit detail.
7. ADMIN export contains only own-company records.
8. Search remains company-scoped.
9. Pagination remains company-scoped.
10. Date/event filters remain company-scoped.

### SUPERADMIN

11. SUPERADMIN can request Company A audit records.
12. SUPERADMIN can request Company B audit records.
13. Company A selection returns only Company A.
14. Company B selection returns only Company B.
15. Missing company context does not return all records.
16. Invalid company ID is handled correctly.
17. SUPERADMIN can retrieve detail for selected company.
18. SUPERADMIN export is restricted to selected company.

### Historical/System Events

19. Historical audit records are correctly attributed to companies.
20. System-generated events receive correct company attribution.
21. Records that cannot be safely attributed are handled explicitly.

---

# 24. Tests — Frontend

Verify:

### SUPERADMIN

```text
Admin Panel
    ↓
Audit Trail
```

Company Dropdown:

```text
✓ visible
✓ populated
✓ correct company names
✓ correct company IDs
```

Select Company A:

```text
✓ Company A records displayed
✗ Company B records
```

Select Company B:

```text
✓ Company B records displayed
✗ Company A records
```

Switching companies:

```text
✓ previous records cleared/replaced
✓ loading state displayed
✓ latest response wins
```

No company:

```text
✓ no unscoped data displayed
✓ appropriate empty state
```

---

# 25. Audit Trail Must Remain Immutable

Do not introduce:

* PUT audit records;
* PATCH audit records;
* DELETE audit records.

The existing audit immutability requirement must remain unchanged.

---

# 26. Performance

Company filtering must be performed in SQL.

Avoid N+1 queries.

If `audit.company_id` is introduced, add an appropriate database index.

If company is derived through a relationship, ensure the query is efficient and indexed appropriately.

Do not load the entire audit table into application memory.

---

# 27. Migration Safety

If a schema migration is required:

1. Create an Alembic migration.
2. Follow existing migration conventions.
3. Add the company relationship/FK correctly.
4. Backfill historical records safely.
5. Do not assign unknown company values arbitrarily.
6. Ensure existing audit records remain immutable.
7. Run migration tests.

Do not modify unrelated tables.

---

# 28. Regression Protection

Do not break:

* existing audit logging;
* authentication audit events;
* security 401/403 audit events;
* document audit events;
* workflow audit events;
* user audit events;
* company audit events;
* audit export;
* audit detail;
* global Roles;
* global Permissions;
* global User Levels.

Use the existing centralized `AuditService.log_event()`.

---

# 29. Verification Commands

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

Review the complete git diff.

Ensure no unrelated files or behavior were changed.

---

# 30. Final Acceptance Criteria

The implementation is complete only when:

## ADMIN — Company A

```text
ADMIN Company A
    ↓
Audit Trail
    ↓
Company A records ONLY
```

## ADMIN — Company B

```text
ADMIN Company B
    ↓
Audit Trail
    ↓
Company B records ONLY
```

## SUPERADMIN

```text
SUPERADMIN
    ↓
Audit Trail
    ↓
Company Dropdown
```

Select:

```text
Company A
```

→ **only Company A Audit Trail records**

Change to:

```text
Company B
```

→ **Company A data is cleared/replaced**

→ **only Company B Audit Trail records are displayed**

SUPERADMIN must never receive an accidental all-company dataset simply because the company parameter is missing.

## Security

```text
ADMIN
    ✗ Cannot access another company's audit records
    ✗ Cannot bypass company scope through query parameters
    ✗ Cannot access another company's audit detail
    ✗ Cannot export another company's audit records

SUPERADMIN
    ✓ Can view any company
    ✓ Must select company context
    ✓ Can view selected company's audit records
```

Finally, report:

1. Root cause of the current Audit Trail company-filtering limitation.
2. How company attribution is determined.
3. Backend/API changes.
4. Frontend changes.
5. Migration changes, if any.
6. Security changes.
7. Tests added.
8. Backend test result.
9. Frontend build/lint result.
10. Any historical audit records that could not be safely assigned to a company.

Do not claim the task is complete unless the actual repository was modified and all relevant verification commands were executed successfully.
