# Spec: Parent Directory Navigation for Subdirectory Grants

## Overview
Users holding only a subdirectory grant (spec 28) get an Access Denied page when opening a parent folder or the category itself, because content-access guards are applied to navigation reads: `GET /categories/{id}` demands a category grant and `GET /directories/{id}` only recognizes upward grant coverage, so both return 404 (which the frontend maps to `/forbidden`). This step introduces read-only navigation access — an ancestor becomes traversable when it contains at least one authorized descendant — without implying content access. The change is guard-level only: no new routes, no schema changes.

## Depends on
Spec 28 subdirectory grants (`user_directory_links`, subtree semantics, pruned `get_tree`), directory hierarchy (`Directory.parent_id`), document visibility + user levels, company scoping, audit trail (`AuditService.log_event()`).

## Routes
No new routes. Changed guard behavior on existing routes:
- `GET /api/v1/directories/{id}` — nav-aware: direct access unchanged; ancestor with an authorized descendant returns 200 with `navigation_only: true`; otherwise 404 — logged-in (`view`)
- `GET /api/v1/directories/category/{id}` and `.../tree` — same pruning as spec 28; nodes now carry `navigation_only` — logged-in (`view`)
- `GET /api/v1/categories/{id}` — category metadata readable when the category holds one of the caller's granted directories (page headers) — logged-in (`view`)
- `GET /api/v1/documents?directory_id=` / `?category_id=` — nav-aware container filter; existing `access_filters` + user-level filter still scope rows, so a nav-only parent returns 200 with 0 items — logged-in (`view`)

## Database changes
No database changes. `navigation_only` is a response-schema field on `DirectoryRead`/`DirectoryNode` only; no migration.

## Templates
No Jinja2 templates — frontend is React/Vite SPA. Frontend changes listed under "Files to change".

## Files to change
- `core/access.py` (new `can_navigate_directory`, `ensure_directory_read_access`, `ensure_category_read_access`, `has_directory_content_access`; `ensure_directory_access` / `ensure_category_access` stay strict)
- `directories/models.py` (`navigation_only: bool = False` on `DirectoryRead`)
- `directories/service.py` (nav-aware `get_directory`; `update_directory` / `delete_directory` call the strict guard directly; `navigation_only` on pruned-tree nodes and partial roots)
- `documents/service.py` (nav-aware `directory_id` / `category_id` list filters; `upload_document` keeps the strict guard)
- `categories/service.py` (`get_category` uses read access; partial-category `directory_count` / `document_count` scoped to granted subtrees)
- `tests/test_directory_access_company.py` (cross-company navigation case)
- `dms-app/src/types/directory.types.ts` (`navigation_only?: boolean`)
- `dms-app/src/pages/DocumentsPage.tsx` (View-only badge, hide Upload CTAs on nav-only folders; keep `/forbidden` for genuine denials)
- `dms-app/src/components/directories/DirectoryTree.tsx` (muted node + eye icon, suppress write context menu on nav-only nodes)

## Files to create
- `tests/test_directory_navigation.py` (parent navigation, listings, sibling denial, write denial, nesting, full-grant regression, user levels, zero-grant, revoke, scoped counts)

## New dependencies
No new dependencies.

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`)
- Each backend module follows: `models.py` (SQLModel + Pydantic read schemas), `schemas.py` (request/response schemas), `service.py` (business logic, class-based, takes Session), `router.py` (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use `CurrentUser` from `core/dependencies.py` for user injection
- Use `AdminUser` for admin-only endpoints
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py` (none needed — no new routes)
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
- Never relax `ensure_directory_access` / `ensure_category_access` — navigation checks apply only to the read paths listed under Routes
- Non-admin denials stay 404 (oracle avoidance); the frontend maps 403/404 to `/forbidden`, so never suppress 404s client-side
- Navigation checks must validate the directory's category is active and same-company server-side, and recompute per request (revoking the last grant removes navigation)
- The `navigation_only` flag is display-only; all content enforcement stays backend

## Definition of done
- [ ] A user granted only a subdirectory can open its category (`GET /categories/{id}` → 200) and traverse parent folders (`navigation_only: true`), reaching the granted directory
- [ ] The tree shows only the authorized ancestor path; siblings are excluded and return 404 on direct access
- [ ] A nav-only parent's document listing returns 200 with 0 items (no error, no leaked rows)
- [ ] Upload, directory rename/delete, and memo attach on nav-only parents stay denied
- [ ] Multi-level nesting, full-category grants, user-level filtering, company isolation, and revoke-removes-navigation all behave as before
- [ ] `pytest tests/test_directory_navigation.py tests/test_directory_access.py tests/test_directory_access_company.py tests/test_category_rbac.py` passes
- [ ] `npm run lint` passes with 0 errors and `npm run build` succeeds
