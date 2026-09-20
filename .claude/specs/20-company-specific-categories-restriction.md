# DMS — Company-Specific Categories & SUPERADMIN Restriction

## Objective

Modify the existing **Categories** module so that categories are strictly **company-specific**.

A category created by an ADMIN must belong to the ADMIN's company and must be available only to users belonging to that same company.

The `categories` table must also record which user created each category through a new `created_by` column.

Additionally, **SUPERADMIN must have no access to the Categories module**. For SUPERADMIN, the Categories page should appear blank/empty, and all category APIs must enforce this restriction server-side.

Before making any changes:

1. Read and follow the repository `AGENTS.md`.
2. Inspect the existing `categories/`, `users/`, `company_profile/`, RBAC, audit, document, and frontend category implementations.
3. Understand the current category schema, service, router, API client, permissions, frontend pages/components, and tests.
4. Reuse the existing multi-company architecture. Do not introduce a parallel company/tenant mechanism.

---

## 1. Category Ownership Model

Categories must become company-specific.

### Required behavior

Each category must belong to exactly one company.

Example:

* Company A has Category A1 and Category A2.
* Company B has Category B1 and Category B2.

Then:

* Company A users can access only A1/A2.
* Company B users can access only B1/B2.
* Company A users must never see B1/B2.
* Company B users must never see A1/A2.

Company isolation must be enforced at the backend/database query level.

Do not rely on frontend filtering.

---

## 2. Database Changes

Inspect the existing `categories` model before modifying it.

Add the following fields as appropriate to the existing schema:

```text
company_id
created_by
```

### `company_id`

`company_id` must reference the existing `companies.id`.

Use the existing company relationship already established through `users.company_id`.

Requirements:

* Foreign key to `companies.id`.
* Category must belong to exactly one company.
* Do not create a duplicate company table or company relationship.
* Add an appropriate database index.
* Do not allow a category to be created without a company.

### `created_by`

Add:

```text
created_by
```

This must reference the existing `users.id`.

Requirements:

* Store the ID of the authenticated ADMIN who created the category.
* Do not accept `created_by` from the frontend request body.
* The backend must always derive it from the authenticated user.
* Add an appropriate foreign key and index.
* Preserve referential integrity.

If the project convention supports ORM relationships, expose the creator relationship where useful for API responses, while avoiding N+1 queries.

---

## 3. Migration & Existing Data

Create a proper Alembic migration.

Do not use `create_all()` as a substitute for production migration.

Before applying `NOT NULL` constraints, inspect existing category records.

If existing categories do not currently have company ownership:

1. Determine a safe and deterministic backfill strategy based on existing data.
2. Do not arbitrarily assign all existing categories to one company.
3. Do not silently assign existing categories to SUPERADMIN.
4. If ownership cannot be determined safely, make the migration fail clearly or use an explicitly documented transitional strategy.
5. Ensure the final schema enforces the required company ownership.

The migration must be safe for production deployment.

---

# 4. Category Creation

Only authorized ADMIN users should be able to create categories according to the existing RBAC model.

When an ADMIN creates a category:

```text
authenticated_user.id -> categories.created_by
authenticated_user.company_id -> categories.company_id
```

The client must not control either value.

### Security requirement

If the request contains:

```json
{
  "company_id": 999,
  "created_by": 123
}
```

the backend must ignore/reject those client-supplied values.

The authenticated user's company is authoritative.

### Company-less ADMIN

If an ADMIN somehow has:

```text
users.company_id = NULL
```

the category creation request must be rejected with an appropriate HTTP error.

Do not create company-less categories.

---

# 5. Category Listing

Modify the category listing service so that results are company-scoped.

### ADMIN

For an ADMIN:

```text
categories.company_id = current_user.company_id
```

must always be applied.

The filter must be applied at the SQL query level before:

* search
* sorting
* pagination
* counting

This prevents data leakage through pagination or query manipulation.

### Example

If:

```text
Company A -> categories 1, 2, 3
Company B -> categories 4, 5, 6
```

an ADMIN belonging to Company A must receive only:

```text
1, 2, 3
```

and never:

```text
4, 5, 6
```

---

# 6. SUPERADMIN — No Category Access

SUPERADMIN must have **no access to Categories**.

This requirement must be enforced at both frontend and backend levels.

### Backend

All category endpoints must reject SUPERADMIN access.

Do not depend only on frontend hiding.

A SUPERADMIN attempting direct API access must receive an appropriate `403 Forbidden`.

Review all category endpoints, including:

* list
* get/detail
* create
* update
* delete/deactivate
* any search endpoint
* any category-related auxiliary endpoint

No category endpoint should expose category data to SUPERADMIN.

### Important

Do not use the existing `AdminUser` dependency alone if it permits SUPERADMIN.

`AdminUser` currently allows both ADMIN and SUPERADMIN, so category-specific authorization must explicitly restrict access to the ADMIN role.

Implement the restriction using the project's existing authorization patterns rather than creating a new authorization framework.

---

# 7. Frontend — SUPERADMIN Categories Page

When the logged-in user is SUPERADMIN:

* Categories page should show blank/empty state.
* Do not display category records.
* Do not display category creation controls.
* Do not display edit/delete controls.
* Do not display company selection for Categories.
* Do not make a category API request unnecessarily.

The UI should behave consistently with the requirement:

> SUPERADMIN has no access to Categories.

Do not show a misleading "All Companies" category view.

---

# 8. Frontend — ADMIN Categories

For ADMIN users:

* Display only categories belonging to the logged-in ADMIN's company.
* Do not provide a Company dropdown for category creation.
* Do not allow the ADMIN to select another company.
* Category creation must automatically associate the authenticated ADMIN's company.
* Display the company only if the existing UI design requires it.

Use the existing API client pattern:

```typescript
import apiClient from './client'
```

Do not introduce `apiRoot` for API requests. The project already uses `apiClient` with `/api/v1` as its base URL.

---

# 9. Category Detail / Update / Delete Security

Every category-specific operation must validate company ownership server-side.

For an ADMIN:

```text
category.company_id == current_user.company_id
```

must be required.

Therefore:

* ADMIN cannot view another company's category.
* ADMIN cannot update another company's category.
* ADMIN cannot delete/deactivate another company's category.
* ADMIN cannot access another company's category by changing the URL ID.
* ADMIN cannot bypass isolation through query parameters.

Return `403 Forbidden` or `404 Not Found` according to the existing project's authorization/resource-not-found convention.

Do not leak whether another company's category exists if the project's security convention requires resource hiding.

---

# 10. Documents and Category Visibility

Inspect all existing document/category relationships.

Company isolation must remain consistent throughout the system.

A user from Company A must not be able to obtain or manipulate Company B's category through:

* document creation
* document update
* document search
* document filtering
* category dropdowns
* memo creation
* workflow-related category selection
* direct API calls

Do not break the existing User Level visibility model.

User Levels remain a document visibility tier and should not be replaced by company filtering.

Company isolation and User Level restrictions must work together.

---

# 11. Audit Trail

Continue using the existing centralized:

```text
AuditService.log_event()
```

Do not create another audit mechanism.

The existing Categories module already participates in centralized audit logging.

Category audit events should correctly identify:

* actor/user
* category
* company context
* operation
* timestamp

For category creation, the actor should be the ADMIN represented by `created_by`.

Do not attribute category activity to SUPERADMIN because SUPERADMIN cannot access Categories.

---

# 12. RBAC

Review `middleware/rbac.py`.

The project uses a hardcoded `ROUTE_PERMISSION_MAP`, so verify all category endpoints are correctly represented in the RBAC layer.

Do not invent new permission verbs.

Reuse:

```text
view
download
create
update
delete
```

where applicable.

However, RBAC alone is not sufficient for company isolation.

The category service must enforce:

```text
ADMIN + current_user.company_id
```

as the tenant boundary.

---

# 13. API Contract

Review existing category request/response schemas.

The API should not expose mutable ownership fields in create/update requests.

### Create request

The frontend should send only category-owned business fields.

It should NOT send:

```text
company_id
created_by
```

The backend derives both values.

### Response

The response may expose:

```text
company_id
created_by
```

if useful for administration/audit purposes, consistent with existing API conventions.

Do not expose sensitive user information unnecessarily.

---

# 14. Search, Sort and Pagination

Company filtering must be applied before all other operations.

Correct logical sequence:

```text
authenticate
    ↓
authorize ADMIN
    ↓
determine current user's company
    ↓
filter categories by company_id
    ↓
apply search
    ↓
apply sorting
    ↓
apply pagination
    ↓
return results + company-scoped count
```

Never:

```text
fetch all categories
    ↓
filter in React
```

or:

```text
paginate all categories
    ↓
filter company
```

because both approaches can leak information or produce incorrect counts.

---

# 15. Frontend State Handling

Ensure category data cannot become stale when:

* logging in as another user
* switching routes
* refreshing the page
* changing user/company context
* receiving a 403 response
* logging out

For SUPERADMIN:

* clear any previously loaded category state
* do not display cached ADMIN category data
* do not reuse category data from another authenticated session

For ADMIN:

* load only the current company's categories.

---

# 16. Tests

Add/update backend tests for all critical security and business rules.

### Database tests

Verify:

* `company_id` exists.
* `created_by` exists.
* Foreign keys are correct.
* Category company ownership is enforced.
* Category creator is correctly stored.

### Creation tests

Verify:

1. Company A ADMIN creates a category.
2. `company_id` automatically becomes Company A.
3. `created_by` automatically becomes that ADMIN's user ID.
4. Client-supplied `company_id` cannot override Company A.
5. Client-supplied `created_by` cannot override the authenticated user.
6. Company-less ADMIN cannot create categories.

### Visibility tests

Verify:

* Company A ADMIN sees Company A categories.
* Company A ADMIN cannot see Company B categories.
* Company B ADMIN sees Company B categories.
* Company B ADMIN cannot see Company A categories.
* Search remains company-scoped.
* Pagination remains company-scoped.
* Count remains company-scoped.

### SUPERADMIN tests

Verify:

* SUPERADMIN cannot list categories.
* SUPERADMIN cannot retrieve a category.
* SUPERADMIN cannot create a category.
* SUPERADMIN cannot update a category.
* SUPERADMIN cannot delete/deactivate a category.
* Direct API requests return `403`.

### Cross-company security tests

Explicitly test:

```text
Company A ADMIN -> GET Company B category ID
Company A ADMIN -> PATCH Company B category ID
Company A ADMIN -> DELETE Company B category ID
```

All must be rejected.

### Frontend tests

Verify:

* ADMIN sees category management UI.
* ADMIN does not see company-selection controls.
* SUPERADMIN sees an empty/blank Categories page.
* SUPERADMIN does not see Create/Edit/Delete controls.
* SUPERADMIN does not unnecessarily call category APIs.
* No stale ADMIN category data appears when the current user is SUPERADMIN.

---

# 17. Regression Testing

After implementation run:

### Backend

```bash
alembic upgrade head
pytest
```

### Frontend

```bash
cd dms-app
npm run build
npm run lint
```

Resolve all failures.

Do not weaken existing tests to make the implementation pass.

---

# 18. Production-Grade Acceptance Criteria

The implementation is complete only when all of the following are true:

* [ ] Categories are company-specific.
* [ ] Every category has a valid `company_id`.
* [ ] Every category has a valid `created_by`.
* [ ] ADMIN-created categories automatically inherit the ADMIN's company.
* [ ] ADMIN-created categories automatically record the authenticated ADMIN as `created_by`.
* [ ] Client cannot override `company_id`.
* [ ] Client cannot override `created_by`.
* [ ] ADMIN can see only categories from their own company.
* [ ] ADMIN cannot access another company's categories through direct API calls.
* [ ] Search is company-scoped.
* [ ] Pagination is company-scoped.
* [ ] Counts are company-scoped.
* [ ] Category CRUD operations enforce company ownership.
* [ ] SUPERADMIN has no category access.
* [ ] SUPERADMIN category API access returns 403.
* [ ] SUPERADMIN Categories UI is blank/empty.
* [ ] SUPERADMIN has no category management controls.
* [ ] No company dropdown is introduced for Categories.
* [ ] Existing User Level functionality remains unchanged.
* [ ] Existing document/category relationships continue to work.
* [ ] Existing audit logging continues through `AuditService.log_event()`.
* [ ] Alembic migration is production-safe.
* [ ] Existing data is handled through an explicit safe migration strategy.
* [ ] Backend tests cover company isolation and SUPERADMIN denial.
* [ ] Frontend build succeeds.
* [ ] Frontend lint succeeds.
* [ ] Full regression test suite passes.

## Final Implementation Rule

Do not make superficial frontend-only changes.

Trace the complete flow:

```text
Authenticated User
      ↓
Role / Authorization
      ↓
User.company_id
      ↓
Category Router
      ↓
Category Service
      ↓
SQL company filter
      ↓
Database
      ↓
Company-scoped response
      ↓
React Category UI
```

The **backend/database must be the ultimate enforcement point** for company isolation.

Do not claim completion unless the implementation has actually been applied and verified against the repository.
