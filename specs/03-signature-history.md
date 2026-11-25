# Spec: Signature & History

## Overview
Phase 3 of the Approval Workflow System implements signature capture (e-signature upload and wet-signature canvas capture) and completes the workflow history ledger. Signatures are stored as file references linked to workflow actions, never mutating the source document. The workflow history provides an immutable, append-only audit trail of all approval events with actor designation snapshots and remarks. This phase completes the data model that Phase 1 (definitions) and Phase 2 (submission/actions) established but left partially implemented — specifically, the signature_id FK on workflow_actions currently references a non-existent signatures table.

## Depends on
- Phase 1 (Foundation) — workflow/ module, migrations, WorkflowDefinitionService, admin config UI
- Phase 2 (Submission) — submit-for-approval, pending queue, ApprovalActionService

## Routes

### New routes (signatures)
- POST /api/v1/signatures — upload e-signature image or wet-signature canvas capture — logged-in (any authenticated user)
- GET /api/v1/signatures/{id} — retrieve signature metadata — logged-in
- GET /api/v1/signatures/{id}/file — serve signature file (binary) — logged-in
- DELETE /api/v1/signatures/{id} — soft-delete own signature — logged-in

### Existing routes (no changes needed)
- GET /api/v1/workflow-instances/{id}/history — already implemented, returns immutable approval history
- POST /api/v1/workflow-instances/{id}/actions — already accepts signature_id parameter (currently optional, will become functional)

## Database changes

### New table: signatures
Create table signatures with columns:
- id (SERIAL PRIMARY KEY)
- user_id (INT NOT NULL REFERENCES users(id))
- file_name (VARCHAR(255) NOT NULL)
- file_path (VARCHAR(512) NOT NULL)
- mime_type (VARCHAR(127) NOT NULL)
- file_size (INT NOT NULL CHECK >= 0)
- sig_type (VARCHAR(20) NOT NULL) — 'e_signature' | 'wet_signature'
- is_active (BOOLEAN NOT NULL DEFAULT TRUE)
- created_at (TIMESTAMP NOT NULL DEFAULT NOW())
- updated_at (TIMESTAMP NOT NULL DEFAULT NOW())

Create index on user_id.

### Constraints
- signatures.file_path follows existing storage/uploads pattern
- signatures.is_active enables soft-delete (actual file retained for audit)
- No FK from workflow_actions.signature_id needs adding — it already exists in the model as Optional[int] (line 184 of workflow/models.py)

## Templates
No Jinja2 templates — frontend is React/Vite SPA.

### Frontend changes
- dms-app/src/components/SignaturePad.tsx — canvas-based wet-signature capture component
- dms-app/src/components/SignatureUpload.tsx — e-signature image upload component
- dms-app/src/pages/PendingApprovalPage.tsx — approval queue with signature attachment
- dms-app/src/pages/ApprovalHistoryPage.tsx — timeline view of workflow history
- dms-app/src/api/workflow.api.ts — add instance action + signature methods
- dms-app/src/types/workflow.types.ts — add Signature + history types

## Files to change

### Backend
| File | Change |
|------|--------|
| workflow/models.py | Add Signature, SignatureType enum, SignatureRead schema |
| workflow/schemas.py | Add SignatureCreate request schema |
| workflow/service.py | Add SignatureService class (upload, retrieve, soft-delete) |
| workflow/router.py | Add signature endpoints (4 routes) |
| core/database.py | Add import workflow.models (already present — verify) |
| middleware/rbac.py | Add (POST, /api/v1/signatures) → CREATE entry |
| conftest.py | Verify existing engine patches cover new module |

### Frontend
| File | Change |
|------|--------|
| dms-app/src/api/workflow.api.ts | Add submitInstance, getInstances, getPendingInstances, actOnInstance, getHistory, uploadSignature methods |
| dms-app/src/types/workflow.types.ts | Add Signature, SignatureCreate, WorkflowInstance, WorkflowAction, WorkflowHistory types |

### New files
| File | Purpose |
|------|---------|
| workflow/signature_service.py | SignatureService — file storage, metadata CRUD, soft-delete |
| migrations/versions/<timestamp>_signatures.py | Alembic migration for signatures table |
| tests/test_signatures.py | Unit tests for SignatureService |
| tests/test_workflow_history.py | Unit tests for history recording |

## New dependencies
No new dependencies. Uses existing FastAPI + SQLModel stack. File storage uses local filesystem (storage/uploads/).

## Rules for implementation

- Use FastAPI + SQLModel only
- Use existing project architecture (backend modules: auth/, users/, categories/, directories/, documents/, user_levels/, audit/, workflow/)
- Each backend module follows: models.py (SQLModel + Pydantic read schemas), schemas.py (request/response schemas), service.py (business logic, class-based, takes Session), router.py (FastAPI router)
- Keep routers thin; business logic belongs in services
- Use CurrentUser from core/dependencies.py for user injection
- Use AdminUser for admin-only endpoints
- Add new endpoints to ROUTE_PERMISSION_MAP in middleware/rbac.py
- Use SQLModel / parameterized queries only
- Use JWT access + refresh token auth (core/security.py)
- Hash passwords with bcrypt 4.0.1 (do not upgrade)
- Python: 4-space indent, snake_case
- TypeScript: 2-space indent, PascalCase components, camelCase hooks/stores
- Frontend API files import apiClient from ./client, not apiRoot from ./base
- Never expose secrets or sensitive data in logs
- Use .env for configuration only (never commit .env)
- Maintain audit trail via AuditService.log_event() (audit/service.py)
- Audit logs are immutable (no PUT/PATCH/DELETE endpoints)
- Tests use SQLite in-memory; patch engine in core.database, middleware.rbac, middleware.audit
- Azure AD: use cryptography library for JWK parsing (not jwk.construct())
- No new dependencies unless explicitly approved
- Add/update tests for every implemented feature
- Signature files stored in storage/uploads/signatures/{user_id}/ directory pattern
- Signature soft-delete sets is_active=False but retains file for audit trail
- WorkflowHistory records are append-only — no PUT/PATCH/DELETE endpoints
- designation_snapshot in history captures the actor's role(s) at time of event
- Every WorkflowAction write must also call AuditService.log_event() via existing _log_audit_action() method

## Definition of done

### Backend
- [ ] POST /api/v1/signatures accepts file upload, stores to disk, returns SignatureRead
- [ ] GET /api/v1/signatures/{id} returns signature metadata (own or admin)
- [ ] GET /api/v1/signatures/{id}/file serves the signature image binary
- [ ] DELETE /api/v1/signatures/{id} soft-deletes own signature (sets is_active=False)
- [ ] POST /api/v1/workflow-instances/{id}/actions with signature_id links signature to action record
- [ ] GET /api/v1/workflow-instances/{id}/history returns immutable timeline with actor names, designation snapshots, and remarks
- [ ] Alembic migration creates signatures table
- [ ] Audit events logged for signature upload, delete, and workflow action with signature
- [ ] RBAC middleware blocks unauthenticated signature access
- [ ] Tests pass: pytest (signature CRUD, history recording, action with signature)

### Frontend
- [ ] SignaturePad.tsx component captures wet-signature via HTML5 canvas
- [ ] SignatureUpload.tsx component allows e-signature image upload
- [ ] Pending approval page shows signature attachment option during approval action
- [ ] Approval history page displays timeline of workflow events
- [ ] npm run build passes without errors
- [ ] npm run lint passes without errors
