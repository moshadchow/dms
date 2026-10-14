# Spec: Subdirectory Level Access Control

## Overview
Allow Admins to grant users access to specific subdirectories within a master category instead of only whole-category grants. A directory grant covers the granted directory and all its descendants (subtree), never siblings. Master-category grants keep their current whole-tree meaning. Effective access is the union of both grant types, enforced in backend services and `core/access.py`, managed through the existing Admin access UI extended with a directory tree.

## Depends on
Category/user grant model (`UserCategoryLink`), directory hierarchy (`Directory.parent_id`), document visibility + user levels, company scoping, audit trail (`AuditService.log_event()`).

## Routes
- `GET /api/v1/users/{id}/directory-access` — read a user's grants (category + directory + effective) — admin (ADMIN + SUPERADMIN read)
- `PUT /api/v1/users/{id}/directory-access` — replace a user's directory grants `{directory_ids}` — admin (ADMIN only for writes; SUPERADMIN writes rejected as with categories)
- `POST /api/v1/users/{id}/directory-access` — idempotent add one grant `{directory_id}` — admin
- `DELETE /api/v1/users/{id}/directory-access/{directory_id}` — revoke one grant — admin
- No new top-level prefix (nested under `/users`, already outside `ROUTE_PERMISSION_MAP`); per-endpoint `AdminUser` guards apply. If a top-level router is added instead, add it to `ROUTE_PERMISSION_MAP`.

## Database changes
New table `user_directory_links` (`user_id` FK `users.id` PK, `directory_id` FK `directories.id` PK, composite PK = duplicate safety, FKs `ON DELETE CASCADE`). No `company_id` column — company resolved via `directory -> category -> company_id`. No changes to existing tables/rows; existing category grants untouched.

## Templates
No Jinja2 templates — frontend is React/Vite SPA. Frontend changes listed under "Files to change".

## Files to change
- `users/models.py` (new `UserDirectoryLink`, `User.directories` relationship, `AssignedDirectoryRead`, `UserRead.directories`, `get_user_with_roles` eager load)
- `core/access.py` (subtree expansion helpers, directory-grant-aware `ensure_directory_access`; `ensure_document_access` inherits via directory)
- `users/service.py` (`_assign_directories`, grant list/set/add/remove + company validation + audit)
- `users/router.py` (4 nested endpoints, thin)
- `directories/service.py` (`list_all`, `list_by_category`, `get_tree` pruning for partial access)
- `documents/service.py` (non-admin list filter = category-grant OR directory-subtree grant; user-level filter unchanged)
- `categories/service.py` (+ `CategoryReadWithStats`: partial categories visible as containers, `access_type`/`granted_directory_ids`)
- `audit/models.py` (new `GRANT_DIRECTORY_ACCESS` / `REVOKE_DIRECTORY_ACCESS` actions)
- `dms-app/src/components/admin/CategoryPermissionPanel.tsx` (expandable per-category directory tree, Full/Inherited vs explicit states)
- `dms-app/src/api/users.api.ts`, `dms-app/src/types/user.types.ts`, `dms-app/src/store/authStore.ts`, `dms-app/src/pages/DocumentsPage.tsx` / `components/directories/DirectoryTree.tsx` (filter to visible subtrees)

## Files to create
- `migrations/versions/<date>_xxxx_add_user_directory_links.py`
- `tests/test_directory_access.py` (behavior + security boundaries)
- `tests/test_directory_access_company.py` (company isolation)

## New dependencies
No new dependencies.

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`)
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` (only if a new top-level prefix is introduced)
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
- Grant semantics: directory grant = directory + all descendants; siblings excluded; category grant = whole tree (unchanged); effective access = union; revocation only removes access with no remaining covering grant
- Never trust client `company_id` or directory↔category claims; validate server-side via `Directory.category.company_id` vs admin's company; NULL-company rows stay invisible to ADMIN/users
- Denied non-admin access returns 404 (existing oracle-avoiding convention), not 403, on category/directory/document guards

## Definition of done
- [ ] Admin can grant one subdirectory via UI; grant persists on reopen
- [ ] Admin can grant multiple subdirectories; authorized user lists/views/downloads docs in them
- [ ] User cannot see/access sibling directories or docs via UI or direct API calls
- [ ] Master-category grants behave exactly as before (whole tree)
- [ ] Revoking one of overlapping grants keeps remaining coverage; revoking last removes access
- [ ] Nested grant covers descendants, not parent/siblings
- [ ] Cross-company grant attempts and directory-ID manipulation rejected
- [ ] User-level, role-permission, company-isolation, audit-trail behavior intact
- [ ] Migration applies via `alembic upgrade head`; tests `tests/test_directory_access*.py` pass; `npm run build` + `npm run lint` clean
