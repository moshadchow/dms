---
description: Create a spec file and feature branch for the next DMS app step
argument-hint: "Step number and feature name e.g. 06 Approval System"
allowed-tools: Read, Write, Glob, Bash(git:*)
---

You are a senior developer spinning up a new feature for the
Document Management System (DMS).
Always follow the rules in AGENTS.md.

User input: $ARGUMENTS

## Step 1 — Parse the arguments
From $ARGUMENTS extract:

1. `step_number` — zero-padded to 2 digits: 2 → 02, 11 → 11

2. `feature_title` — human readable title in Title Case
   - Example: "Registration" or "Login and Logout"

3. `feature_slug` — git and file safe slug
   - Lowercase, kebab-case
   - Only a-z, 0-9 and -
   - Maximum 40 characters
   - Example: registration, login-logout


If you cannot infer these from $ARGUMENTS, ask the user
to clarify before proceeding.


## Step 2 — Research the codebase
Read these files before writing the spec:
- `AGENTS.md` — roadmap, conventions, schema, module structure
- `main.py` — existing routes and middleware registration
- `core/database.py` — existing schema and engine configuration
- `core/dependencies.py` — CurrentUser, AdminUser, require_permission
- `core/config.py` — Settings class and environment variables
- `seed.py` — existing roles and permissions
- `middleware/rbac.py` — ROUTE_PERMISSION_MAP (must add new endpoints here)
- `middleware/audit.py` — audit logging middleware
- All files in `.opencode/specs/` — avoid duplicating existing specs

Check `AGENTS.md` to confirm the requested step is not already
marked complete. If it is, warn the user and stop.

## Step 3 — Write the spec
Generate a spec document with this exact structure:

---
# Spec: <feature_title>

## Overview
One paragraph describing what this feature does and why
it exists at this stage of the DMS roadmap.

## Depends on
Which previous steps this feature requires to be complete.

## Routes
Every new route needed:
- `METHOD /path` — description — access level (public/logged-in/admin)

If no new routes: state "No new routes".

## Database changes
Any new tables, columns, or constraints needed.
Always verify against `core/database.py` before writing this.
If none: state "No database changes".

## Templates
No Jinja2 templates — frontend is React/Vite SPA.
If frontend changes needed, list them under "Files to change".

## Files to change
Every file that will be modified.

## Files to create
Every new file that will be created.

## New dependencies
Any new pip packages or npm packages. If none: state "No new dependencies".

## Rules for implementation
Specific constraints Claude must follow. Always include:
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`)
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py`
- Use SQLModel / parameterized queries only
- Use JWT access + refresh token auth (core/security.py)
- Hash passwords with bcrypt 4.0.1 (do not upgrade)
- Python: 4-space indent, `snake_case`
- TypeScript: 2-space indent, `PascalCase` components, `camelCase` hooks/stores
- Frontend API files import `apiClient` from `./client`, not `apiRoot` from `./base`
- Never expose secrets or sensitive data in logs
- Use `.env` for configuration only (never commit `.env`)
- Maintain audit trail via `AuditService.log_event()` (audit/service.py)
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints)
- Tests use SQLite in-memory; patch `engine` in `core.database`, `middleware.rbac`, `middleware.audit`
- Azure AD: use `cryptography` library for JWK parsing (not `jwk.construct()`)
- No new dependencies unless explicitly approved
- Add/update tests for every implemented feature

## Definition of done
A specific testable checklist. Each item must be
something that can be verified by running the app.
---

## Step 4 — Save the spec
Save to: `.opencode/specs/<step_number>-<feature_slug>.md`

## Step 5 — Report to the user
Print a short summary in this exact format:
```
Branch:    <branch_name>
Spec file: .opencode/specs/<step_number>-<feature_slug>.md
Title:     <feature_title>
```

Then tell the user:
"Review the spec at `.opencode/specs/<step_number>-<feature_slug>.md`
then enter Plan Mode with Shift+Tab twice to begin implementation."

Do not print the full spec in chat unless explicitly asked.
