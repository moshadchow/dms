# Spec: Document Sorting and Filtering

## Overview
This feature enhances the document listing endpoint (`GET /api/v1/documents`) with flexible sorting and additional filtering capabilities. Currently, documents are only sorted by `created_at` descending with no way to change the sort field or direction. Users need to sort by title, file name, file size, or update date, and filter by uploader or date ranges to efficiently find documents in large repositories.

## Depends on
- Spec 01: Approval Workflow System (document module exists)
- Spec 29: Parent Directory Navigation (directory/category filtering in place)
- Document module with existing `list_documents` service and router

## Routes
No new routes. Modifies existing:
- `GET /api/v1/documents` — enhanced with `sort_by`, `sort_order`, `uploaded_by`, `created_from`, `created_to`, `updated_from`, `updated_to` query parameters — access level: logged-in (VIEW permission)

## Database changes
No database changes. All sorting/filtering uses existing columns on `documents` table and joins to `users` (for uploader) and `directories`/`categories` (already joined).

## Templates
No Jinja2 templates — frontend is React/Vite SPA. Frontend changes under "Files to change".

## Files to change
- `documents/schemas.py` — extend `DocumentFilterParams` with sort/filter fields
- `documents/service.py` — update `list_documents` to apply sorting and new filters
- `documents/router.py` — pass new query parameters to service
- `dms-app/src/types/document.types.ts` — extend `DocumentListParams` interface
- `dms-app/src/api/documents.api.ts` — pass new params in list call (no code change needed if params spread)

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

### Sorting Implementation Details
- **Allowed sort fields**: `title`, `file_name`, `file_size`, `created_at`, `updated_at`
- **Sort order**: `asc` | `desc` (default: `desc` for dates, `asc` for text/size)
- **Validation**: Reject invalid `sort_by` values with 422; default to `created_at` + `desc`
- **Secondary sort**: Always add `id` as tiebreaker for stable pagination

### Filtering Implementation Details
- `uploaded_by` (int): filter by uploader user ID (admin sees all; non-admin only sees uploaders within their accessible documents)
- `created_from` / `created_to` (datetime): inclusive date range on `created_at`
- `updated_from` / `updated_to` (datetime): inclusive date range on `updated_at`
- Date params accept ISO 8601 strings; timezone-naive treated as UTC

### Access Control
- Non-admin users: all new filters scoped by existing access logic (category grants + directory grants + user level links)
- `uploaded_by` filter for non-admins: only returns documents they already have access to that happen to be uploaded by that user
- Date filters apply after access scoping

## Definition of done
- [ ] Backend: `GET /api/v1/documents` accepts `sort_by`, `sort_order`, `uploaded_by`, `created_from`, `created_to`, `updated_from`, `updated_to`
- [ ] Backend: Invalid `sort_by` returns 422 with clear error message
- [ ] Backend: Sorting works correctly for all allowed fields (asc/desc)
- [ ] Backend: New filters return correct results and respect company/access scoping
- [ ] Backend: Pagination remains stable with secondary `id` sort
- [ ] Frontend: `DocumentListParams` type includes all new fields
- [ ] Frontend: Documents page UI exposes sort dropdown and advanced filter panel
- [ ] Tests: Unit tests for sorting logic in `DocumentService.list_documents`
- [ ] Tests: Integration tests for each new filter parameter
- [ ] Tests: Test non-admin access scoping with new filters
- [ ] Tests: Test invalid sort_by returns 422
- [ ] Run `pytest tests/test_documents.py -q` passes
- [ ] Run `cd dms-app && npm run build` passes (typecheck)
- [ ] Run `cd dms-app && npm run lint` passes