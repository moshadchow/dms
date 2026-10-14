# Spec: Office Memo Drafting

## Overview
Add an Office Memo document type to the DMS, giving users a structured drafting experience for internal memos with standard fields (To, From, Date, Subject, Body). Memos are first-class documents that carry memo-specific metadata, support optional file attachments, allow the author to attach an e-signature or wet-signature before submission, and route through the existing approval workflow on submit. Approvers retain the authority to modify the draft and attach or apply their own signature prior to final approval. This feature builds directly on top of the completed workflow/ module, documents/ module, and signature infrastructure.

## Depends on
- Phase 1-3 workflow backend: workflow/ module (definitions, instances, actions, signatures, history) -- complete
- documents/ module (upload, storage, metadata, user-level visibility) -- complete
- signature infrastructure (SignatureService, e_signature / wet_signature types) -- complete
- audit/ module (AuditService.log_event()) -- complete
- categories/ module -- complete
- directories/ module -- complete
- user_levels/ module -- complete
- Frontend infrastructure (apiClient, Zustand auth store, ProtectedRoute, AppLayout) -- complete
- Spec 01 (approval workflow system) -- complete
- Spec 02 (submission) -- complete
- Spec 03 (signature & history) -- complete
- Spec 04 (frontend approval workflow) -- complete

## Routes

### Backend (new)
- `POST /api/v1/memos` -- Create a memo draft (creates document + memo metadata, optionally uploads attachments) -- logged-in (create permission)
- `GET /api/v1/memos` -- List memos authored by or visible to current user -- logged-in (view permission)
- `GET /api/v1/memos/{memo_id}` -- Get memo detail with metadata, attachments, and workflow status -- logged-in (view permission)
- `PATCH /api/v1/memos/{memo_id}` -- Update memo metadata (title, subject, recipients, body, status) -- logged-in (update permission, owner only)
- `POST /api/v1/memos/{memo_id}/submit` -- Submit memo for approval (creates workflow instance, attaches signature if provided) -- logged-in (create permission, owner only)
- `GET /api/v1/memos/{memo_id}/attachments` -- List attachment metadata for a memo -- logged-in (view permission)

### Frontend routes
- `GET /memos` -- Memo list page -- logged-in
- `GET /memos/new` -- Memo drafting form -- logged-in
- `GET /memos/:id` -- Memo detail view with workflow status -- logged-in
- `GET /memos/:id/edit` -- Edit memo draft -- logged-in (owner only)

## Database changes

New table: `memos`

```sql
CREATE TABLE memos (
    id              SERIAL PRIMARY KEY,
    document_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    to_recipients   VARCHAR(500) NOT NULL,
    from_name       VARCHAR(255) NOT NULL,
    memo_date       TIMESTAMP NOT NULL DEFAULT NOW(),
    subject         VARCHAR(255) NOT NULL,
    body            TEXT,
    is_submitted    BOOLEAN NOT NULL DEFAULT FALSE,
    signature_id    INTEGER REFERENCES signatures(id) ON DELETE SET NULL,
    created_by      INTEGER NOT NULL REFERENCES users(id),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
```

Columns:
- `document_id` -- FK to documents.id; the memo is a document with additional metadata
- `to_recipients` -- comma-separated or structured list of recipient names/emails
- `from_name` -- author display name (denormalized for memo format)
- `memo_date` -- the memo date (may differ from created_at)
- `subject` -- memo subject line
- `body` -- memo body text (plain text or markdown)
- `is_submitted` -- draft vs. submitted state
- `signature_id` -- FK to signatures.id; author's signature attached at submission time
- `created_by` -- FK to users.id; the memo author

No existing tables require modification.

## Templates
No Jinja2 templates -- frontend is React/Vite SPA.

## Files to change

### Backend
1. `core/database.py` -- add `import memos.models` in `create_db_and_tables()` so the new table is auto-created in DEBUG mode
2. `middleware/rbac.py` -- add ROUTE_PERMISSION_MAP entries for new memo routes:
   - `(POST, "/api/v1/memos")` -> PermissionAction.CREATE
   - `(PATCH, "/api/v1/memos")` -> PermissionAction.UPDATE
3. `documents/service.py` -- no changes needed; memo creation delegates to DocumentService for file upload
4. `workflow/service.py` -- no changes needed; memo submission delegates to WorkflowInstanceService

### Frontend
1. `dms-app/src/pages/MemoListPage.tsx` -- list of user's memos with status badges
2. `dms-app/src/pages/MemoDraftPage.tsx` -- memo drafting/editing form with To, From, Date, Subject, Body, attachments, signature picker
3. `dms-app/src/pages/MemoDetailPage.tsx` -- read-only memo view with workflow timeline and attachment downloads
4. `dms-app/src/components/memo/MemoForm.tsx` -- reusable memo form component
5. `dms-app/src/components/memo/SignaturePicker.tsx` -- select existing signature or trigger upload
6. `dms-app/src/components/memo/AttachmentUploader.tsx` -- multi-file upload for supporting documents
7. `dms-app/src/api/memo.api.ts` -- API client for memo endpoints (uses apiClient from ./client)
8. `dms-app/src/types/memo.types.ts` -- TypeScript interfaces for Memo, MemoCreate, MemoRead, MemoListResponse
9. `dms-app/src/App.tsx` -- add /memos, /memos/new, /memos/:id, /memos/:id/edit routes

## Files to create

### Backend (new module: `memos/`)
1. `memos/__init__.py` -- empty
2. `memos/models.py` -- SQLModel table `Memo`, read schemas (MemoRead, MemoListResponse, MemoDetailRead)
3. `memos/schemas.py` -- request schemas (MemoCreate, MemoUpdate, MemoSubmit)
4. `memos/service.py` -- MemoService class: create_draft, get_memo, list_memos, update_memo, submit_memo
5. `memos/router.py` -- FastAPI router mounted at /api/v1/memos

## New dependencies
No new pip packages or npm packages.

## Rules for implementation
- Use FastAPI + SQLModel only
- Use existing project architecture: backend modules follow models.py / schemas.py / service.py / router.py pattern
- Keep routers thin; business logic belongs in MemoService
- MemoService uses `CurrentUser` from `core/dependencies.py` for user injection
- Add new endpoints to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py`
- Memo creation: upload supporting files via DocumentService, create Memo record linking to the document
- Memo submission: call WorkflowInstanceService.submit_instance() with the memo's document_id and the selected workflow_definition_id; attach signature_id to the workflow action
- Approvers can edit the draft: PATCH /api/v1/memos/{id} is owner-only at the memo level, but approvers act through the workflow action endpoint with remarks indicating changes. If full draft editing by approvers is desired, add an approver-edit check in MemoService (anyone in the current step's eligible approver list can PATCH)
- Use SQLModel / parameterized queries only
- Use JWT access + refresh token auth (core/security.py)
- Python: 4-space indent, snake_case
- TypeScript: 2-space indent, PascalCase components, camelCase hooks/stores
- Frontend API files import apiClient from ./client, not apiRoot from ./base
- Never expose secrets or sensitive data in logs
- Use .env for configuration only (never commit .env)
- Maintain audit trail via AuditService.log_event() for memo create, update, submit events
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints on audit records)
- Tests use SQLite in-memory; patch engine in core.database, middleware.rbac, middleware.audit
- No new dependencies unless explicitly approved
- Add/update tests for every implemented feature
- Existing seed data does not change; memo drafting uses existing roles (Maker creates, Checker updates, Auditor views)
- Default admin: admin@dms.local / Admin@1234

## Definition of done
- [ ] `memos/` module created with models, schemas, service, router
- [ ] `memos` table created via Alembic migration (or auto-created in DEBUG mode)
- [ ] `POST /api/v1/memos` creates a memo draft with document upload, returns MemoRead
- [ ] `GET /api/v1/memos` lists memos with pagination, filtered by user visibility
- [ ] `GET /api/v1/memos/{id}` returns memo detail including attachments and workflow status
- [ ] `PATCH /api/v1/memos/{id}` updates memo metadata (owner only)
- [ ] `POST /api/v1/memos/{id}/submit` creates workflow instance and routes to approval
- [ ] Signature attachment: submit endpoint accepts optional signature_id, validates ownership
- [ ] Approver actions: approvers can approve/reject/return with remarks via existing workflow action endpoint
- [ ] Audit events logged for memo create, update, submit
- [ ] RBAC middleware updated with new route prefixes
- [ ] Frontend: MemoDraftPage renders memo form with To, From, Date, Subject, Body fields
- [ ] Frontend: MemoDraftPage supports multi-file attachment upload
- [ ] Frontend: MemoDraftPage has signature picker (select existing or upload new)
- [ ] Frontend: MemoListPage shows user's memos with status badges
- [ ] Frontend: MemoDetailPage shows memo content, attachments, and workflow timeline
- [ ] Frontend: routes registered in App.tsx (/memos, /memos/new, /memos/:id, /memos/:id/edit)
- [ ] pytest passes with all existing tests plus new memo tests
- [ ] npm run build succeeds (tsc + vite)
- [ ] npm run lint passes
