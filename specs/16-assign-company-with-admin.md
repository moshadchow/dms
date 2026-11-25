Act as a **Senior Backend & Frontend Engineer** working on the existing DMS application.

## Mandatory First Step

Before making any change:

1. Read `AGENTS.md` completely.
2. Inspect the existing DMS backend and frontend codebase.
3. Identify the current implementation of:

   * `users` model
   * `roles` model and RBAC
   * SUPERADMIN role
   * User creation API
   * User creation service/business logic
   * New User frontend form
   * User Level API and dropdown
   * Authentication/current-user handling
   * Company Profile model/API created previously
   * AuditService
   * Alembic migrations
   * Existing tests
4. Follow the existing architecture and conventions.
5. Do not make assumptions about model/table/field names until they are verified from the codebase.

Repository guidance requires reuse of the existing RBAC permission model and frontend `apiClient`, and states that new protected endpoints must be incorporated into the RBAC route map where applicable.

---

# Goal

Customize the existing **New User** form specifically for a **SUPERADMIN** user.

When the authenticated user is `SUPERADMIN` and creates an `ADMIN` user:

### Remove

* User Level dropdown

### Add

* Company Profile dropdown

The selected Company Profile must be associated with the newly created ADMIN user.

This functionality must be isolated to the SUPERADMIN user-management flow and **must not change the existing behavior of other business roles/logins**.

---

# Functional Requirements

## 1. SUPERADMIN New User Form

When the logged-in user has role:

`SUPERADMIN`

the New User form must:

### Remove

The existing:

`User Level`

field/dropdown.

It must not be displayed, populated, validated, or submitted for a SUPERADMIN-created ADMIN user.

### Add

A:

`Company Profile`

dropdown.

The dropdown must load available **active companies** from the existing Company Profile functionality.

Each option should display an appropriate human-readable company name/short name while submitting the company's unique ID.

Do not create duplicate company data or a second company-management implementation.

---

# 2. Role Restriction

The SUPERADMIN is allowed to create **ADMIN users only**, according to the existing SUPERADMIN requirement.

Therefore, when creating a user from the SUPERADMIN New User form:

* Role must be `ADMIN`.
* The SUPERADMIN must not be able to create:

  * MAKER
  * CHECKER
  * AUDITOR
  * SUPERADMIN
  * Any other role

Do not rely on frontend restrictions alone.

The backend must independently enforce this rule.

---

# 3. Company Assignment

When SUPERADMIN creates an ADMIN:

```text
ADMIN
  |
  +-- Company Profile
          |
          +-- Selected Company
```

The selected company must be persisted against the ADMIN user using the most appropriate database relationship based on the existing codebase.

Before implementing this, inspect whether the existing `users` model already contains a company relationship/foreign key.

### If no company relationship exists

Add an appropriate company reference to the existing `users` table, preferably:

```text
company_id -> companies.id
```

using the existing SQLModel/Alembic conventions.

Do not create a separate user-company mapping table unless the existing business model genuinely requires many-to-many company assignment.

For the current requirement, assume **one ADMIN belongs to one Company Profile**, unless the existing codebase demonstrates otherwise.

---

# 4. Backend API Changes

Inspect the existing user creation API before modifying it.

Extend the existing user creation request/response schemas to support company assignment where appropriate.

For example:

```text
company_id: optional/required depending on role
```

Do not blindly make `company_id` globally required.

### Required behavior

For SUPERADMIN-created ADMIN:

* `company_id` is required.
* The selected company must exist.
* The selected company must be active.
* The company must be persisted with the created ADMIN.

For existing business users/roles:

* Preserve the current request/response behavior.
* Do not suddenly require `company_id`.
* Do not alter existing User Level behavior.

---

# 5. Server-Side Security

The backend must determine the authenticated user's role from the authenticated session/token.

Do not trust a frontend-provided value such as:

```text
created_by_role=SUPERADMIN
```

or:

```text
is_superadmin=true
```

Authorization must be derived from the authenticated user.

Implement the business rules at the service/API layer:

### SUPERADMIN

Can:

* Create ADMIN
* Assign ADMIN to an active company

Cannot:

* Create non-ADMIN roles
* Assign SUPERADMIN role
* Assign MAKER/CHECKER/AUDITOR
* Bypass company validation

### ADMIN / other business roles

Existing behavior must remain unchanged.

Do not introduce regressions into existing user creation.

---

# 6. Company Dropdown API

Inspect the previously implemented Company Profile API.

Reuse it if an appropriate endpoint already exists.

The frontend should retrieve only companies that are valid for assignment.

Prefer:

```text
GET active companies
```

rather than retrieving inactive companies and filtering only in the browser.

If the existing Company API is SUPERADMIN-only for all operations, provide the minimum necessary read endpoint/authorization behavior required by the New User form without weakening company-management security.

The endpoint must not expose unnecessary company information.

---

# 7. Frontend Behavior

Inspect the existing New User component/page.

Implement role-aware rendering.

Conceptually:

```text
if currentUser.role === SUPERADMIN:
    show ADMIN role
    show Company Profile
    hide User Level
else:
    preserve existing form
```

However, use the application's actual role constants/types rather than hardcoded strings where available.

### SUPERADMIN UI

Display:

* User fields already required by the existing form
* Role = ADMIN
* Company Profile dropdown

Do not display:

* User Level

### Other users

Preserve the existing form exactly as much as possible.

Do not remove User Level or introduce Company Profile behavior for other business roles unless already required by the existing implementation.

---

# 8. Direct API Manipulation Protection

A SUPERADMIN should not be able to bypass the UI and submit:

```json
{
  "role": "MAKER",
  "company_id": 1
}
```

and successfully create a MAKER.

Likewise, an ADMIN or other role must not be able to submit a forged `company_id` to obtain unauthorized company assignment.

All relevant business rules must be enforced server-side.

---

# 9. Existing User Level Behavior

This change is specifically for the SUPERADMIN New User form.

Do not globally remove User Level functionality.

The existing User Level module and behavior for:

* ADMIN
* MAKER
* CHECKER
* AUDITOR

must remain intact unless the inspected codebase proves that the new company relationship requires a specific compatible adjustment.

The repository documentation confirms that User Levels are part of document visibility and must continue to be enforced through the existing architecture.

---

# 10. Audit

Reuse the existing `AuditService`.

When SUPERADMIN creates an ADMIN and assigns a company, ensure the existing user-creation audit event captures the relevant operation.

Do not create another audit mechanism.

The existing repository specifically requires significant user operations to use `AuditService.log_event()`.

---

# 11. Database Migration

If a `company_id` field must be added to `users`:

Create an Alembic migration following the existing migration conventions.

Requirements:

* Foreign key to the existing Company table.
* Appropriate index if justified.
* Nullable for existing users/business roles if necessary for backward compatibility.
* Existing users must continue to work.
* Do not break existing data.

Do not create a migration if the existing schema already supports the required relationship.

---

# 12. Validation

Implement validation for:

### SUPERADMIN → ADMIN

```text
role = ADMIN
company_id != null
company exists
company is active
```

Reject:

```text
company_id = nonexistent
company_id = inactive company
role != ADMIN
missing company_id
```

Use the application's existing HTTP status codes and error response conventions.

---

# 13. Frontend Error Handling

The Company Profile dropdown must handle:

* Loading state
* Empty company list
* API failure
* Inactive company filtering
* Required-field validation
* Backend validation errors

If there are no active companies available, clearly communicate that an active Company Profile must be created before an ADMIN can be assigned.

Do not silently submit an ADMIN without a company.

---

# 14. Tests

Inspect the existing test framework and fixtures first.

Add tests for:

### Backend

1. SUPERADMIN can create ADMIN with a valid active company.
2. SUPERADMIN cannot create MAKER.
3. SUPERADMIN cannot create CHECKER.
4. SUPERADMIN cannot create AUDITOR.
5. SUPERADMIN cannot create another SUPERADMIN.
6. SUPERADMIN cannot create ADMIN without company.
7. SUPERADMIN cannot assign an invalid company.
8. SUPERADMIN cannot assign an inactive company.
9. Created ADMIN contains the correct company relationship.
10. Existing ADMIN user creation behavior is unchanged.
11. Existing MAKER/CHECKER/AUDITOR behavior is unchanged.
12. Existing User Level behavior remains unchanged.

### Frontend

Verify:

1. SUPERADMIN sees Company Profile.
2. SUPERADMIN does not see User Level in New User form.
3. SUPERADMIN can select an active Company Profile.
4. SUPERADMIN is restricted to ADMIN role.
5. ADMIN does not receive the SUPERADMIN-specific Company Profile behavior.
6. Existing business roles retain their current New User form behavior.
7. Company API errors are displayed properly.

Follow the repository's SQLite in-memory testing conventions. The project documentation specifies that tests use SQLite + StaticPool and that database engines imported by modules must be patched appropriately in test fixtures.

---

# 15. Regression Protection

This is a targeted SUPERADMIN enhancement.

**Do not modify behavior for other business logins.**

Explicitly verify that:

* Existing authentication remains unchanged.
* Azure AD/JIT provisioning remains unchanged.
* Existing role permissions remain unchanged.
* Existing User Level functionality remains unchanged.
* Existing Admin functionality remains unchanged.
* Existing Maker/Checker/Auditor functionality remains unchanged.
* Existing Company Profile management remains SUPERADMIN-only.

The frontend must continue using the existing `apiClient` pattern rather than introducing another API client.

---

# 16. Implementation Quality

Follow the existing project conventions:

### Backend

* FastAPI
* SQLModel
* Pydantic schemas
* Service-layer business logic
* Existing dependencies
* Existing RBAC
* Existing audit mechanism
* Alembic

### Frontend

* React 18
* TypeScript
* Existing API architecture
* Existing components
* Existing form patterns
* Existing styling conventions

Do not add unnecessary dependencies.

Do not refactor unrelated code.

Do not duplicate existing Company Profile or User Level functionality.

---

# 17. Final Verification

After implementation:

1. Review all changed files.
2. Review the database migration.
3. Review the user creation service.
4. Review backend authorization.
5. Review frontend role-based rendering.
6. Verify SUPERADMIN → ADMIN → Company assignment.
7. Verify User Level is absent only from the SUPERADMIN New User form.
8. Verify other business logins are unaffected.
9. Run backend tests.
10. Run frontend lint.
11. Run frontend build.
12. Review the final diff for unrelated modifications.

Report:

* Files created/modified
* Database changes
* API changes
* User/company relationship
* SUPERADMIN authorization changes
* Frontend changes
* Tests added/updated
* Test/build/lint results
* Any assumptions discovered from the actual codebase

**Do not claim completion unless the implementation has actually been made and verified against the real source code.**
