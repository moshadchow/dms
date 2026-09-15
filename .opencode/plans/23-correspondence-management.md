# Spec: Correspondence Management

## Overview
Correspondence Management tracks official communications — inbound letters, outbound responses, and internal circulars — as first-class entities in the DMS. Each correspondence record wraps a `Document` (auto-created HTML file, like memos) with communication-specific metadata: reference number, direction, correspondent details, priority, and response tracking. Correspondence follows the same workflow approval pattern as memos: draft → submit → approve → final PDF with embedded signatures.

## Depends on
- Memos module (pattern reference — correspondence mirrors its architecture)
- Workflow module (for approval routing)
- Signatures module (for author/approver signatures in final PDF)
- Document module (backing store, visibility via user levels)
- Company Profile module (company scoping)
- Audit module (trail logging)

## Routes

### Correspondence CRUD
- `POST /api/v1/correspondences` — create draft — logged-in (CREATE)
- `GET /api/v1/correspondences` — list (paginated, filtered) — logged-in
- `GET /api/v1/correspondences/{id}` — detail — logged-in
- `PATCH /api/v1/correspondences/{id}` — update draft — logged-in (UPDATE)
- `POST /api/v1/correspondences/{id}/submit` — submit for workflow approval — logged-in (CREATE)
- `GET /api/v1/correspondences/{id}/download-final-draft` — download approved PDF — logged-in

### Reference Number
- `GET /api/v1/correspondences/next-reference` — generate next reference number for a company — logged-in

No new public routes. All routes go through JWT auth + RBAC middleware.

## Database changes

### New table: `correspondences`

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | `int` | PK, auto | |
| `document_id` | `int` | FK `documents.id`, NOT NULL, unique, indexed | 1:1 with Document |
| `created_by` | `int` | FK `users.id`, NOT NULL | Author |
| `company_id` | `int?` | FK `companies.id`, indexed | Company scoping |
| `reference_number` | `str(50)` | NOT NULL, unique, indexed | Auto-generated per company |
| `subject` | `str(255)` | NOT NULL, indexed | |
| `body` | `str(50000)` | default `""` | HTML from rich-text editor |
| `direction` | `enum` | NOT NULL, indexed | `inbound`, `outbound`, `internal` |
| `priority` | `enum` | NOT NULL, default `normal` | `low`, `normal`, `high`, `urgent` |
| `correspondent_name` | `str(255)` | nullable | Sender/recipient name |
| `correspondent_organization` | `str(255)` | nullable | External org name |
| `correspondent_email` | `str(255)` | nullable | |
| `correspondent_phone` | `str(50)` | nullable | |
| `date_sent` | `datetime?` | nullable | When correspondence was sent (outbound) |
| `date_received` | `datetime?` | nullable | When correspondence was received (inbound) |
| `response_required` | `bool` | default `false` | |
| `response_deadline` | `datetime?` | nullable | |
| `response_received` | `bool` | default `false` | |
| `author_signature_id` | `int?` | FK `signatures.id`, nullable | Author's signature |
| `workflow_instance_id` | `int?` | FK `workflow_instances.id`, nullable | Set on submit |
| `created_at` | `datetime` | default `utcnow` | |
| `updated_at` | `datetime` | default `utcnow` | |

**New enums** (defined in `correspondence/models.py`):
- `CorrespondenceDirection(str, Enum)`: `inbound`, `outbound`, `internal`
- `CorrespondencePriority(str, Enum)`: `low`, `normal`, `high`, `urgent`

### New Alembic migration
Creates the `correspondences` table with all columns, indexes, unique constraint on `document_id` and `reference_number`.

## Templates
No Jinja2 templates — frontend is React/Vite SPA.

### Frontend files to change
- `dms-app/src/types/correspondence.types.ts` — new TypeScript interfaces
- `dms-app/src/api/correspondence.api.ts` — new API client module
- `dms-app/src/pages/CorrespondenceListPage.tsx` — list page with filters (direction, priority, status, search)
- `dms-app/src/pages/CorrespondenceDetailPage.tsx` — detail/edit/submit page
- `dms-app/src/components/correspondence/CorrespondenceForm.tsx` — create/edit form (direction, priority, correspondent info, body editor)
- `dms-app/src/components/correspondence/CorrespondenceFilters.tsx` — filter panel
- `dms-app/src/App.tsx` — add routes for correspondence pages
- `dms-app/src/components/layout/Sidebar.tsx` — add "Correspondence" nav item

## Files to change

### Backend
- `audit/models.py` — add `AuditAction` values: `CREATE_CORRESPONDENCE`, `UPDATE_CORRESPONDENCE`, `SUBMIT_CORRESPONDENCE`, `DOWNLOAD_CORRESPONDENCE_DRAFT`
- `audit/models.py` — add `AuditModule.CORRESPONDENCE = "correspondence"`
- `core/database.py` — add `import correspondence.models` in `create_db_and_tables()`
- `main.py` — register `correspondence_router` at `/api/v1/correspondences`
- `middleware/rbac.py` — add entries to `ROUTE_PERMISSION_MAP`:
  - `("GET", "/api/v1/correspondences")` → `VIEW`
  - `("POST", "/api/v1/correspondences")` → `CREATE`
  - `("PATCH", "/api/v1/correspondences")` → `UPDATE`

### Frontend
- (see Frontend files to change above)

## Files to create

### Backend
- `correspondence/__init__.py`
- `correspondence/models.py` — `Correspondence`, `CorrespondenceDirection`, `CorrespondencePriority`, read schemas (`CorrespondenceRead`, `CorrespondenceDetailRead`, `CorrespondenceListResponse`)
- `correspondence/schemas.py` — `CorrespondenceCreate`, `CorrespondenceUpdate`, `CorrespondenceSubmit`
- `correspondence/service.py` — `CorrespondenceService` (create_draft, get, list, update, submit, generate_final_draft, generate_reference_number)
- `correspondence/router.py` — FastAPI router
- `correspondence/pdf_generator.py` — PDF generation for final drafts (reportlab, mirrors `memos/pdf_generator.py`)
- `migrations/versions/<timestamp>_add_correspondences_table.py` — Alembic migration

### Frontend
- (see Frontend files to change above)

### Tests
- `tests/test_correspondence.py` — CRUD, access control, workflow integration, PDF generation

## New dependencies
No new dependencies. Uses existing: `reportlab` (PDF), `bleach` (HTML sanitization), `sqlmodel`, `fastapi`.

## Rules for implementation
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
- Correspondence reference numbers auto-generated per company: `COR-{company_short_name}-{YYYY}-{sequence}` (e.g., `COR-ACME-2026-000042`)
- Body content is sanitized HTML via `bleach.clean()` (same whitelist as memos)
- HTML stored as standalone file on disk at `STORAGE_ROOT/<company>/correspondence/<user_id>/<uuid>.html`
- Document record created automatically (FileType.HTML, mime_type="text/html")
- Workflow integration via `WorkflowInstanceService.submit_instance()` (same as memos)
- Final PDF embeds: correspondence metadata table, HTML body, author signature, approver signatures in workflow order, approval info section
- Access control: admin bypass; author can edit in non-terminal status; eligible approvers can edit in draft/returned/rejected; view requires document access + user level match
- List access: non-admin sees own correspondence only; ADMIN sees own company's; SUPERADMIN sees all
- Company scoping: `company_id` from author's company; storage paths use company short_name
- Response tracking: `response_required`, `response_deadline`, `response_received` fields — frontend highlights overdue items
- Priority shown as colored badge in list view (low=gray, normal=blue, high=orange, urgent=red)

## Definition of done
1. `POST /api/v1/correspondences` creates a correspondence draft with auto-generated reference number, HTML file on disk, Document record, and user level links
2. `GET /api/v1/correspondences` returns paginated list filtered by direction, priority, status, and search — respects company scoping
3. `GET /api/v1/correspondences/{id}` returns full detail with correspondent info, workflow status, and user level IDs
4. `PATCH /api/v1/correspondences/{id}` updates draft fields; regenerates HTML if body changes
5. `POST /api/v1/correspondences/{id}/submit` creates a workflow instance and transitions status to `submitted`
6. `GET /api/v1/correspondences/{id}/download-final-draft` returns PDF only when workflow status is `approved`
7. `GET /api/v1/correspondences/next-reference` returns the next available reference number for the user's company
8. Admin bypasses all access checks; non-admin sees only own records; ADMIN sees own company's records
9. Audit events logged for create, update, submit, and download actions
10. All existing tests still pass (`pytest`)
11. Frontend list page displays correspondences with direction badge, priority indicator, response status, and reference number
12. Frontend detail page shows full correspondence with body preview, correspondent info, and workflow status
13. Frontend form supports create/edit with direction selector, priority selector, correspondent fields, and rich-text body editor
14. `npm run build` passes (TypeScript typecheck + Vite build)
15. `npm run lint` has no new errors in correspondence files
