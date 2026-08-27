# Repository Guidelines

## Project Structure
FastAPI backend (repo root) + React/Vite frontend (`dms-app/`). Backend feature modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`, `workflow/`, `memos/`, `signatures/`, `storage_usage/`. Shared infra in `core/`. Middleware in `middleware/`. RBAC models re-exported from `rbac/models.py` (canonical: `users/models.py`). Migrations in `migrations/`. Bootstrap data in `seed.py`. Frontend source in `dms-app/src/` organized by concern (`api/`, `components/`, `hooks/`, `pages/`, `store/`, `types/`, `utils/`).

## Backend: Key Commands
```
alembic upgrade head          # apply DB migrations (required before first run)
python seed.py                # seed roles, permissions, and admin user (run once after migrate)
uvicorn main:app --reload     # dev server on :8000
pytest                        # run all tests (176 tests, SQLite-in-memory)
```

**`DEBUG=True` bypasses Alembic** — `main.py` lifespan calls `create_db_and_tables()` when DEBUG is true, auto-creating tables from SQLModel metadata. In production, rely solely on `alembic upgrade head`.

## Frontend: Key Commands
```
cd dms-app && npm install
npm run dev      # Vite dev server on :5173 (proxies /api to backend :8000)
npm run build    # tsc + vite build
npm run lint     # ESLint
```

Frontend env: `dms-app/.env` sets `VITE_API_BASE_URL=/api`. The `@` alias resolves to `dms-app/src/`. Frontend uses Tailwind CSS (via `@tailwind` directives in `index.css`); no `tailwind.config.js` exists — utilities are used directly.

## Testing: SQLite In-Memory
Tests use `SQLite` + `StaticPool` (in-memory), **not** PostgreSQL. The `conftest.py` fixture monkeypatches the engine in three places:
- `core.database.engine`
- `middleware.rbac.engine`
- `middleware.audit.engine`

Any new module that imports `engine` directly (e.g., for a new middleware) must be patched in the test fixture or tests will hit the wrong database.

## RBAC Middleware: Hardcoded Route Map
`middleware/rbac.py` has a `ROUTE_PERMISSION_MAP` dict mapping `(HTTP_METHOD, path_prefix)` to a `PermissionAction`. **New endpoints that require permission checks must be added here**, otherwise they are silently unprotected by the middleware (individual endpoint guards via `require_permission()` still apply, but the middleware safety net is bypassed).

Paths under `/api/v1/auth`, `/docs`, `/redoc`, `/openapi.json`, and `/health` bypass RBAC entirely (`PUBLIC_PATH_PREFIXES`).

## Backend Module Convention
Each feature module follows this pattern:
- `models.py` — SQLModel ORM models + Pydantic read schemas
- `schemas.py` — additional request/response schemas (optional, some modules keep all schemas in models.py)
- `service.py` — business logic (class-based, takes `Session`)
- `router.py` — FastAPI router

The `documents/` module has two service classes: `DocumentService` and `DocumentVariantService`.

The `workflow/` module has three router objects in `router.py`: `router` (workflow definitions, mounted at `/api/v1/workflows`), `instance_router` (workflow instances, mounted at `/api/v1/workflow-instances`), and `signature_router` (signatures, mounted at `/api/v1/signatures`). Service classes are split into separate files: `definition_service.py`, `instance_service.py`, `approval_service.py`. The old `service.py` is a backward-compatible re-export shim. Shared approver logic lives in `approval_policy.py`.

The `memos/` module creates document drafts with markdown rendering and workflow integration. Its service uses `core/access.py` helpers (`ensure_directory_access`, `ensure_document_access`, `ensure_document_user_level_access`) for permission checks.

**Memo edit access rules** (`memos/service.py` `_check_edit_access`):
- Admin always bypasses
- Terminal statuses (`approved`, `published`, `cancelled`, `archived`) → no edits allowed
- Author can edit in any non-terminal status (`draft`, `submitted`, `pending_approval`, `returned`, `rejected`)
- Eligible approvers can edit in `draft`, `returned`, `rejected` status only (not `submitted`/`pending_approval`)
- `MemoUpdate` schema includes optional `signature_id` field for updating the author's signature before approval

The `memos/` module has a PDF generator (`memos/pdf_generator.py`) for final draft downloads. It converts markdown to reportlab XML. **Gotcha:** Reportlab's `Paragraph` parser is strict about balanced XML tags — the markdown-to-XML conversion (`_apply_inline_formatting`) strips italic markers to plain text (instead of generating `<i>` tags) to avoid malformed nesting. A `_sanitize_for_reportlab()` safety net removes empty/malformed tags before rendering.

## Audit Trail Module
`audit/` records all significant user and system activities. Key details:
- **`audit/service.py`** — `AuditService.log_event()` is the single centralized method. It uses its own `Session(engine)` to write audit logs independently of the caller's transaction, ensuring logs are committed even if the outer transaction rolls back. Never raises on failure.
- **`middleware/audit.py`** — auto-logs auth events, security events (401/403), and document operations from HTTP requests. Registered after RBAC middleware in `main.py`.
- **`audit/router.py`** — admin-only endpoints: `GET /api/v1/audit-logs` (list), `GET /api/v1/audit-logs/{id}` (detail), `GET /api/v1/audit-logs/export` (CSV).
- **Immutability**: no PUT/PATCH/DELETE endpoints exist for audit records. Users cannot edit or delete audit logs.
- **Instrumentation**: `auth/service.py`, `users/service.py`, `documents/service.py`, `directories/service.py`, `categories/service.py`, `user_levels/service.py`, `memos/service.py` all call `AuditService.log_event()` after significant operations.
- **Legacy**: `core/audit.py` contains an old logger-based `log_audit_event` helper. It is dead code — all callers now use `AuditService`. Do not add new callers; use `AuditService` directly.

## Auth & User Injection
Use the `CurrentUser` annotated type from `core/dependencies.py` to inject the authenticated user into endpoints:
```python
from core.dependencies import CurrentUser
def my_endpoint(current_user: CurrentUser = None): ...
```

`AdminUser` (also from `core/dependencies.py`) raises 403 for non-admins.

## Azure AD Authentication
Backend module: `auth/azure_service.py` handles PKCE, token exchange, ID token validation, and JIT user provisioning.

**Key files:**
- `auth/router.py` — `/azure/login`, `/azure/callback`, `/azure/config` endpoints
- `auth/azure_service.py` — Azure token exchange, ID token validation, user resolution
- `core/config.py` — `AZURE_*` and `FRONTEND_URL` settings
- `dms-app/src/pages/AzureCallbackPage.tsx` — frontend callback handler

**Azure callback flow:** Login → Azure → callback exchanges code for tokens → validates ID token → resolves/creates user → redirects to `{FRONTEND_URL}/auth/callback?access_token=...&refresh_token=...`

**Error surfacing:** `azure_callback` in `auth/router.py` has separate `except HTTPException` and `except Exception` handlers. In DEBUG mode, the actual error message is URL-encoded in the `?error=` query param. Audit events go to `dms.auth` logger.

**JWK parsing:** `python-jose`'s `jwk.construct()` fails with Azure AD signing keys that include `x5c` fields. `azure_service.py:188-203` uses the `cryptography` library to build RSA public keys from the X.509 certificate chain instead. Do not revert to `jwk.construct()`.

Azure is enabled when all three of `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_TENANT_ID` are set. Copy `.env.example` to `.env` for local setup.

## Frontend Auth Flow
- Zustand store (`store/authStore.ts`) persists only tokens to localStorage; the `user` object is re-fetched on every page load via `ProtectedRoute` calling `authApi.me()`.
- Axios client (`api/client.ts`) automatically intercepts 401 responses, attempts a single token refresh, and redirects to `/login` on failure.
- Azure AD: `LoginPage.tsx` link → backend `/azure/login` → Azure → callback → `AzureCallbackPage.tsx` stores tokens → fetches user → navigates to dashboard.

## Frontend API Pattern
All API files import `apiClient` from `./client` (the Axios instance with interceptors), **not** `apiRoot` from `./base` (a plain string). The `apiClient` has `baseURL` set to `/api/v1`, so paths are relative: `apiClient.get('/users')`.

## User Levels
`user_levels/` module manages document visibility tiers. Documents are linked to user levels via `DocumentUserLevelLink`. Users can only see documents linked to their level (enforced in `documents/service.py`). Admin bypasses all level restrictions.

## Dependency Pins
- `bcrypt==4.0.1` — passlib 1.7.4 is incompatible with bcrypt 4.1+. Do not upgrade.
- `python-jose[cryptography]==3.3.0` — used for JWT and OIDC (JWK parsing replaced with `cryptography` for Azure AD keys).
- `httpx==0.27.0` — used for Azure AD token exchange (async HTTP client).
- Frontend: React 18, Vite 5, Zustand 4, React Router 6.

## Seed Data
`seed.py` creates four roles with fixed permission matrices:
| Role    | Permissions |
|---------|------------|
| Admin   | view, download, create, update, delete |
| Maker   | view, download, create, update |
| Checker | view, download, update |
| Auditor | view, download |

Default admin: `admin@dms.local` / `Admin@1234`.

## Docker (Stale)
`docker-compose.yml` references `./backend` and `./frontend` directories that don't match the current repo layout. There is a root `Dockerfile` but docker-compose needs fixing before use.

## Coding Style
4-space indent in Python, 2-space in TypeScript/TSX. `snake_case` for Python, `PascalCase` for React components, `camelCase` for hooks/stores/utils.

## Commits & PRs
Short imperative subjects (`Fix archieve & Restore feature`). PRs: clear summary, migration notes for schema changes, screenshots for UI.

## Security
Copy `.env.example` to `.env` for local setup. Never commit `.env` (it contains Azure AD client secrets). GitHub secret scanning will reject pushes containing Azure secrets. Treat `storage/uploads/` as runtime data. Ensure `__pycache__/` and `*.pyc` are in `.gitignore` before committing.

---

## Approval Workflow System

Generic, document-type-agnostic approval engine. Reuses `auth/`, RBAC, `users/`, `user_levels/`, `audit/`, `documents/`, `directories/`. No new auth, permission, or audit mechanisms — extend the existing ones.

### Workflow Module Structure
`workflow/` follows the standard module convention. Service classes:
- `WorkflowDefinitionService` — CRUD for workflow templates (admin-configured, not hardcoded)
- `WorkflowInstanceService` — starts/tracks a workflow run against a document
- `ApprovalActionService` — approve / reject / return / clarify / forward
- `SignatureService` — stores e-signature (uploaded image) or wet-signature (canvas capture) as a file reference, never mutates the source document

**Note:** Workflow definitions are category-agnostic. The `document_category_id` field was removed from `WorkflowDefinition`. Category filtering is handled at the document level, not the workflow level.

### Workflow Status Enum
`draft` → `submitted` → `pending_approval` → (`returned` | `rejected` | `approved` | `cancelled`) → `published` (optional) → `archived`

### RBAC Integration
Add new prefixes to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py`:
- `(POST, /api/v1/workflows)` → admin-only config actions
- `(POST, /api/v1/workflow-instances)` → create (Maker)
- `(POST, /api/v1/workflow-instances/{id}/actions)` → update (Checker/approver tiers)
- `(GET, /api/v1/workflow-instances/pending)` and `/mine` → view

Reuse existing role permission matrix (`view`, `download`, `create`, `update`, `delete`) — do not invent new permission verbs. Approver eligibility is enforced via `workflow_step_approvers`, on top of RBAC, not instead of it.

**RBAC gap on PATCH /activate:** `PATCH /api/v1/workflows/{id}/activate` has no `ROUTE_PERMISSION_MAP` entry — it is protected solely by the `AdminUser` dependency. This has no practical impact since admin bypasses RBAC anyway, but for defense-in-depth an entry could be added.

### User Level Integration
`workflow_instances` inherits the visibility rules already enforced in `documents/service.py` via `DocumentUserLevelLink`. Admin bypass still applies. Approval never overrides a User Level restriction — an approver who cannot view the underlying document per their level must not appear as a valid approver for that instance.

### Instance Snapshot & Lifecycle
- **Instance snapshot:** `WorkflowInstanceService.submit_instance()` snapshots the workflow definition's steps at creation time. Definition changes (step order, approvers, approval mode) do **not** affect running instances — only future submissions use the updated definition.
- **Deactivation:** Deactivating a definition (`DELETE /api/v1/workflows/{id}`) blocks new submissions only. Existing instances continue through their approval chain to completion.
- **Multiple active workflows per category:** The system allows multiple active workflow definitions for the same document category. The Phase 2 submission UI should present a dropdown when multiple definitions exist for a document's category.

### Workflow Audit
`workflow_history` is the approval-specific ledger (level, designation, signature ref); `audit/` remains the system-wide event log. Every `workflow_actions` write must also call `AuditService.log_event()` — do not build a second audit mechanism.

### Workflow Test Fixture Impact
Any new module importing `engine` directly (e.g. a workflow-specific middleware, if added) must be patched in `conftest.py` alongside `core.database.engine`, `middleware.rbac.engine`, `middleware.audit.engine`.

### Design Decisions (Implementation Notes)
- **Activation validation:** Activating a workflow (`PATCH /{id}/activate`) does **not** validate that steps/approvers exist. A workflow with no steps can be activated.
- **Step order uniqueness:** Enforced by a DB unique constraint on `(workflow_definition_id, step_order)`. The service does not pre-check for duplicates — a raw DB integrity error would surface if violated.
- **Step ordering in detail response:** `GET /api/v1/workflows/{id}` returns steps in DB fetch order, not explicitly sorted by `step_order`. For deterministic ordering, add `.order_by(WorkflowStep.step_order)` to the query.
