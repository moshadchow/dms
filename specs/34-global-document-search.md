# Spec: Global Document Search Across All Accessible Directories

## Overview
This feature enables users to search for documents across **all directories they have access to** without first navigating into a specific directory. Currently, the `GET /api/v1/documents` endpoint requires a `directory_id` (frontend enforces this) and returns only documents within that directory or category. Users need a "global search" capability to find documents by title, filename, or content across their entire accessible document repository — scoped by their category grants, directory grants, and user level links. This is essential for large repositories where users may not remember which directory a document resides in.

## Depends on
- Spec 29: Parent Directory Navigation (directory/category access logic)
- Spec 33: Document Sorting and Filtering (sorting/filtering infrastructure in place)
- Document module with existing `list_documents` service and router

## Routes
Modifies existing route:
- `GET /api/v1/documents` — enhanced to support global search when `directory_id` and `category_id` are both omitted; returns documents across all accessible directories/categories for the user — access level: logged-in (VIEW permission)

No new routes. The existing endpoint already accepts optional `directory_id` and `category_id`; the change is semantic — when both are omitted, the query scopes to **all accessible directories** instead of returning empty/error.

## Database changes
No database changes. All access control uses existing joins to `directories`, `categories`, `UserCategoryLink`, `UserDirectoryLink`, and `DocumentUserLevelLink`.

## Templates
No Jinja2 templates — frontend is React/Vite SPA. Frontend changes under "Files to change".

## Files to change
- `documents/service.py` — modify `list_documents` to handle "no directory_id, no category_id" case for non-admins (scope to all granted categories + directory subtrees)
- `documents/router.py` — no code change needed (parameters already optional)
- `middleware/rbac.py` — add entry for `GET /api/v1/documents` without directory prefix (already covered by existing `("/api/v1/documents", VIEW)`)
- `dms-app/src/pages/DocumentsPage.tsx` — add global search mode (search without selecting a directory first), new UI entry point (e.g., header search bar or dedicated page)
- `dms-app/src/api/documents.api.ts` — no change needed (params already spread)
- `dms-app/src/types/document.types.ts` — no change needed (types already support optional directory_id/category_id)

## Files to create
None

## New dependencies
No new dependencies.

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`)
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` (not needed — existing mapping covers `/api/v1/documents`)
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

### Access Control Logic for Global Search
When `directory_id` and `category_id` are both `None`:
- **Admin**: sees all active documents in their company (existing behavior when no filters)
- **Non-admin**: scope to union of:
  1. All categories granted via `UserCategoryLink` (category-level grants)
  2. All directory subtrees granted via `UserDirectoryLink` (directory-level grants, including descendants)
- Then apply user-level visibility filter (`DocumentUserLevelLink` matching `current_user.user_level_id`)
- Then apply other filters (search, file_type, uploaded_by, date ranges, sorting)

This reuses the exact same access logic already in `list_documents` (lines 155-201 in service.py), just without the `directory_id`/`category_id` narrowing.

### Frontend UX
- Add a "Global Search" toggle or dedicated page accessible from dashboard/header
- When in global search mode, show documents from all accessible directories
- Directory tree navigation still available for browsing; global search is for finding
- Reuse existing sorting, filtering, and pagination controls

## Definition of done
- [ ] Backend: `GET /api/v1/documents` without `directory_id`/`category_id` returns documents across all accessible directories for non-admin users
- [ ] Backend: Admin users see all company documents when no directory/category specified
- [ ] Backend: All existing filters (search, file_type, uploaded_by, date ranges, sorting) work in global search mode
- [ ] Backend: Access control correctly scopes results (category grants + directory grants + user levels)
- [ ] Frontend: Documents page has a "Global Search" mode accessible without selecting a directory first
- [ ] Frontend: Global search shows directory path/category for each result so users know where documents live
- [ ] Tests: Unit test for `list_documents` global search access scoping (non-admin)
- [ ] Tests: Integration test for global search with various filter combinations
- [ ] Tests: Test cross-company isolation (user only sees own company documents)
- [ ] Run `pytest tests/test_documents.py -q` passes (extend existing test file)
- [ ] Run `cd dms-app && npm run build` passes (typecheck)
- [ ] Run `cd dms-app && npm run lint` passes