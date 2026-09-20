Act as a **Senior Backend & Frontend Engineer** working on the existing DMS application.

Before making any changes, **read `AGENTS.md` and thoroughly inspect the existing codebase**. Follow the established architecture, coding conventions, authentication, RBAC, audit, database migration, API, and frontend patterns. Do not introduce a parallel implementation or make unrelated changes.

Repository guidelines:

## Goal

Implement a **Company Profile / Company Setup** module that allows only **SUPERADMIN** users to manage company information.

The Company Profile form must contain:

* `Company ID`
* `Full Name`
* `Short Name`
* `Address`
* `Contact Person`
* `Contact No`
* `Email Address`

---

## Backend Requirements

### 1. Company Model

Create a new `Company` model following the existing SQLModel/database architecture.

The model should contain appropriate fields for:

* Company ID
* Full Name
* Short Name
* Address
* Contact Person
* Contact No
* Email Address
* Active/Inactive status
* Created timestamp
* Updated timestamp

Follow the existing naming conventions and timestamp/status patterns used throughout the project.

### 2. Database Migration

Create an Alembic migration for the new `Company` table if required by the existing schema.

The migration must:

* Create the company table.
* Apply appropriate primary key/unique constraints.
* Add indexes where justified.
* Support active/inactive company status.
* Follow the existing migration conventions.

Do not modify existing tables unnecessarily.

### 3. Company API

Create a dedicated Company module following the existing project structure, for example:

* `companies/models.py`
* `companies/schemas.py` if required
* `companies/service.py`
* `companies/router.py`

Implement APIs for:

* Create Company
* Get Company / Company List
* Get Company by ID
* Update Company
* Activate/Deactivate Company

Use the existing `CurrentUser`, `AdminUser`, RBAC, validation, error handling, and service-layer conventions.

### 4. SUPERADMIN Authorization

Company Profile management must be **strictly restricted to `SUPERADMIN`**.

Only a `SUPERADMIN` can:

* Create a company.
* View company configuration.
* Update company information.
* Activate a company.
* Deactivate a company.

An `ADMIN` user must receive **403 Forbidden** when attempting to access Company Profile APIs.

Do not rely on frontend visibility for security. Authorization must be enforced server-side.

Reuse the existing RBAC architecture rather than introducing a new authorization mechanism.

Inspect `middleware/rbac.py` and update `ROUTE_PERMISSION_MAP` where required so the new endpoints are not unintentionally left unprotected.

If the existing permission model cannot express the Super Admin-only requirement, use the project's established dependency/service authorization pattern rather than creating a new permission system.

### 5. Business Rules

Implement appropriate validation:

* `Company ID` must be unique.
* `Short Name` should be unique if consistent with the business/domain model.
* Required fields must be validated.
* Email Address must use proper email validation.
* Contact No must follow reasonable existing validation conventions.
* Inactive companies must remain stored and must not be physically deleted.
* Deactivation should be a soft-status change.
* Updating an inactive company must follow a clearly defined rule consistent with the existing architecture.

Do not invent business rules that conflict with existing code. Where the existing codebase does not define a rule, choose the simplest production-safe behavior and document the assumption.

### 6. Audit Trail

Use the existing `AuditService.log_event()` mechanism.

Audit at minimum:

* Company creation
* Company update
* Company activation
* Company deactivation

Do not create a separate audit implementation.

---

# Frontend Requirements

## 1. Company Profile Page

Create a dedicated **Company Profile** management page using the existing React + TypeScript architecture and UI conventions.

The page should provide:

* Company list/table if multiple companies are supported by the backend.
* Create Company action.
* Edit Company action.
* Activate/Deactivate action.
* Appropriate confirmation dialogs for status changes.
* Loading states.
* Empty states.
* API error handling.
* Success feedback.
* Form validation.

Use the existing frontend API client:

`apiClient` from `dms-app/src/api/client.ts`

Do not use `apiRoot` directly.

## 2. Company Form

Create a clean, production-grade Company Profile form containing:

* Company ID
* Full Name
* Short Name
* Address
* Contact Person
* Contact No
* Email Address

Display validation errors clearly.

The form must support both:

* Create
* Edit/Update

Use the application's existing UI components, styling conventions, and form patterns wherever available.

## 3. SUPERADMIN Menu Access

The **Company Profile** menu/navigation option must be visible **only to SUPERADMIN**.

For `ADMIN` users:

* Do not display the Company Profile menu.
* Do not display Company management actions.
* Do not provide any direct navigation option to the page.

However, frontend hiding is only a UX restriction. Backend APIs must independently enforce SUPERADMIN authorization.

## 4. Admin Restrictions

An `ADMIN` user must have **no Company Profile option anywhere in the frontend**.

Verify:

* Sidebar/navigation
* Dashboard shortcuts
* User-management screens
* Routes
* Buttons/actions
* Direct URL access

If an Admin manually navigates to the Company Profile route, the frontend should display the application's existing unauthorized/403 behavior rather than exposing the management page.

---

# API Integration

Create a dedicated frontend API service following the existing project pattern, such as:

`dms-app/src/api/companies.ts`

Use the existing `apiClient` and `/api/v1` base URL convention.

Ensure request/response types are strongly typed with TypeScript.

---

# Testing Requirements

Inspect the existing test architecture before implementing tests.

Add tests covering at minimum:

### Backend

* SUPERADMIN can create a company.
* SUPERADMIN can retrieve company information.
* SUPERADMIN can update company information.
* SUPERADMIN can deactivate a company.
* SUPERADMIN can reactivate a company.
* ADMIN cannot create a company.
* ADMIN cannot update a company.
* ADMIN cannot deactivate/activate a company.
* Unauthenticated users cannot access Company APIs.
* Duplicate Company ID is rejected.
* Invalid email is rejected.
* Required fields are validated.
* Company deactivation does not physically delete the record.
* Audit events are generated for significant company-management operations.

### Frontend

Verify that:

* SUPERADMIN can see Company Profile in navigation.
* SUPERADMIN can access the Company Profile page.
* SUPERADMIN can create/edit company information.
* SUPERADMIN can activate/deactivate a company.
* ADMIN cannot see Company Profile navigation.
* ADMIN cannot access the Company Profile route.
* API errors are handled correctly.
* Form validation works correctly.

Follow the existing SQLite in-memory test setup and project-specific fixture conventions documented in `AGENTS.md`.

---

# Security & Architecture Constraints

* **Read `AGENTS.md` first.**
* Inspect the existing code before implementation.
* Reuse existing authentication and RBAC.
* Do not create a second authentication mechanism.
* Do not create a separate Super Admin authorization framework.
* Do not bypass existing `CurrentUser` or RBAC patterns.
* Do not rely solely on frontend restrictions.
* Do not expose sensitive information.
* Do not commit `.env` or credentials.
* Do not modify unrelated modules.
* Maintain backward compatibility with existing users and roles.
* Follow the existing Python and TypeScript coding standards.
* Keep the implementation modular and production-ready.

---

# Important Existing Context

The system already contains a `SUPERADMIN` role as part of the RBAC implementation. **Inspect the actual current implementation before making assumptions about its model, permissions, or user relationship.**

The existing project uses:

* FastAPI
* SQLModel
* Alembic
* React
* TypeScript
* Axios
* Existing RBAC middleware
* Existing `AuditService`
* Existing authentication dependencies

Extend these mechanisms instead of replacing them.

---

# Final Validation

Before considering the implementation complete:

1. Read and follow `AGENTS.md`.
2. Inspect all relevant existing backend and frontend code.
3. Implement the Company model and migration.
4. Implement Company APIs.
5. Enforce SUPERADMIN-only authorization server-side.
6. Implement the Company Profile frontend.
7. Add SUPERADMIN-only navigation and routing.
8. Ensure ADMIN users have no Company Profile option.
9. Add/update backend and frontend tests.
10. Run the relevant test suite and frontend build/lint checks.
11. Review the complete diff for unintended changes.
12. Verify that existing authentication, RBAC, users, and audit functionality continue to work.

At the end, provide a concise implementation summary including:

* Files created/modified
* Database migration details
* API endpoints
* SUPERADMIN authorization behavior
* Frontend changes
* Tests added/updated
* Validation/build results
* Any assumptions or limitations discovered from the existing codebase
