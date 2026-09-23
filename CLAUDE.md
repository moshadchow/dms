# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## Project Structure

Dual-app repo: **FastAPI backend** at repo root + **React + Vite frontend** in `dms-app/`.

Backend modules: `auth/`, `users/`, `categories/`, `directories/`, `documents/`, `user_levels/`, `audit/`, `workflow/`, `memos/`, `signatures/`, `storage_usage/`, `notifications/`, `company_profile/`, `correspondence/`. Shared infra in `core/`. Middleware in `middleware/`. RBAC models re-exported from `rbac/models.py` (canonical: `users/models.py`). Migrations in `migrations/`. Bootstrap data in `seed.py`. Frontend source in `dms-app/src/` organized by concern (`api/`, `components/`, `hooks/`, `pages/`, `store/`, `types/`, `utils/`).

Backend features follow a consistent module convention:
- `models.py` — SQLModel ORM models + Pydantic read schemas
- `service.py` — Business logic (class-based, takes `Session`)
- `router.py` — FastAPI router
- `schemas.py` — Additional request/response schemas (where separate from models)

## Commands

### Backend (Python / FastAPI)
```bash
alembic upgrade head          # Apply DB migrations (required before first run)
python seed.py                # Seed roles, permissions, admin user (run after migrate)
uvicorn main:app --reload     # Dev server on :8000
pytest                        # Run all tests (SQLite in-memory)
pytest tests/path/to/test.py  # Single test file
pytest tests/foo/test_bar.py::test_baz  # Single test function
ruff check . && black .       # Lint / format
```

### Frontend (dms-app)
```bash
cd dms-app && npm install
npm run dev       # Vite dev server on :5173 (proxies /api to backend)
npm run build     # tsc + vite build (includes typecheck)
npm run lint      # ESLint
```

## High-Level Architecture

- **API surface**: All endpoints under `/api/v1`. Public paths (`/api/v1/auth`, `/docs`, `/redoc`, `/openapi.json`, `/health`) bypass RBAC.
- **Auth**: JWT access + refresh tokens. Azure AD (Microsoft Entra ID) integration via PKCE. `python-jose` for JWT; `cryptography` for Azure JWK/X.509 parsing (do NOT revert to `jwk.construct()`).
- **RBAC**: Two-layer defense: (1) `middleware/rbac.py` `ROUTE_PERMISSION_MAP` maps `(HTTP_METHOD, path_prefix)` → `PermissionAction`; (2) per-endpoint `require_permission()` guards in `core/dependencies.py`.
- **Audit**: `AuditService.log_event()` is the authoritative audit sink. Uses an independent `Session(engine)` so logs persist even if caller rolls back. Immutable records — no PUT/PATCH/DELETE endpoints.
- **DB**: SQLModel ORM. SQLite for tests (`StaticPool`). PostgreSQL in production. `create_db_and_tables()` only runs when `DEBUG=True` — production must use `alembic upgrade head`.
- **Frontend**: Zustand stores for auth/workflow/theme, Axios `apiClient` with automatic 401 refresh interceptor, React Router with protected routes.

## Critical Cross-File Rules

### Tests
Tests use SQLite in-memory with `StaticPool`. `conftest.py` monkeypatches `engine` in three places:
- `core.database.engine`
- `middleware.rbac.engine`
- `middleware.audit.engine`
If you add a new module that imports `engine` at import time, update `conftest.py` or use lazy access.

### RBAC
New routes **must** be added to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py`, or the middleware silently skips protection for unknown prefixes. Paths under `/api/v1/auth`, `/docs`, `/redoc`, `/openapi.json`, and `/health` bypass RBAC entirely.

### Dependency Pins
- `bcrypt==4.0.1` — passlib 1.7.4 breaks with bcrypt 4.1+
- `python-jose[cryptography]==3.3.0`
- `httpx==0.27.0`

### Frontend
- Import `apiClient` from `./client`, not `apiRoot` from `./base`
- Use `getErrorMessage()` for error display
- `npm run build` includes `tsc` typecheck — no separate typecheck script
- Frontend env: `dms-app/.env` sets `VITE_API_BASE_URL=/api`. The `@` alias resolves to `dms-app/src/`. Frontend uses Tailwind CSS (via `@tailwind` directives in `index.css`); no `tailwind.config.js` exists — utilities are used directly.

### Dependency Injection
Use `CurrentUser` from `core/dependencies.py` for authenticated user injection. `AdminUser` allows both ADMIN and SUPERADMIN. `SuperAdminUser` restricts to SUPERADMIN only.

### Azure AD JWKs
`auth/azure_service.py` constructs RSA public keys from `x5c` certificate chains using the `cryptography` library. Do not revert to `python-jose.jwk.construct()`.

### Audit Trail
Always use `AuditService.log_event()` for significant operations. Never create alternate audit sinks.

### Notable Module Details
- **Documents**: Has two service classes: `DocumentService` and `DocumentVariantService`
- **Workflow**: Has three router objects in `router.py`: `router` (workflow definitions), `instance_router` (workflow instances), and `signature_router` (signatures). Service classes are split into separate files: `definition_service.py`, `instance_service.py`, `approval_service.py`.
- **Memos**: Uses markdown-to-reportlab XML conversion with special handling for italic markers to avoid malformed nesting.
- **User Levels**: Documents are linked to user levels via `DocumentUserLevelLink`. Users can only see documents linked to their level (enforced in `documents/service.py`). Admin bypasses all level restrictions.
- **Company Profile**: Multi-tenancy foundation. SUPERADMIN-only endpoints at `/api/v1/companies`. Azure AD config endpoints: `GET/PUT/DELETE /api/v1/companies/{id}/azure-config` — PUT/DELETE are superadmin-only, GET allows admin for own company or superadmin for any.
- **Storage Usage**: Tracks storage consumption per user/company. Admin endpoints at `/api/v1/storage`.
- **Correspondence**: Manages incoming, outgoing, and internal correspondence with file attachments. `document_id` on `Correspondence` is nullable. Outbound/internal auto-generate an HTML backing document from `body` text.

### Approval Workflow System
Generic, document-type-agnostic approval engine. Reuses existing auth, RBAC, users, user_levels, audit, documents, directories. No new auth, permission, or audit mechanisms.

- **Workflow Status**: `draft` → `submitted` → `pending_approval` → (`returned` | `rejected` | `approved` | `cancelled`) → `published` (optional) → `archived`
- **RBAC Integration**: Add new prefixes to `ROUTE_PERMISSION_MAP` in `middleware/rbac.py`:
  - `(POST, /api/v1/workflows)` → admin-only config actions
  - `(POST, /api/v1/workflow-instances)` → create (Maker)
  - `(POST, /api/v1/workflow-instances/{id}/actions)` → update (Checker/approver tiers)
  - `(GET, /api/v1/workflow-instances/pending)` and `/mine` → view
- **User Level Integration**: `workflow_instances` inherits visibility rules from `documents/service.py` via `DocumentUserLevelLink`. Admin bypass still applies.
- **Instance Snapshot**: `WorkflowInstanceService.submit_instance()` snapshots the workflow definition's steps at creation time. Definition changes do **not** affect running instances.
- **Workflow Audit**: Every `workflow_actions` write must also call `AuditService.log_event()` — do not build a second audit mechanism.

### Seed Data
`seed.py` creates five roles with fixed permission matrices:
- SuperAdmin: view, download, create, update, delete (full system access)
- Admin: view, download, create, update, delete
- Maker: view, download, create, update
- Checker: view, download, update
- Auditor: view, download
Default admin: `admin@dms.local` / `Admin@1234`.

### Coding Style
4-space indent in Python, 2-space in TypeScript/TSX. `snake_case` for Python, `PascalCase` for React components, `camelCase` for hooks/stores/utils.

### Security
Copy `.env.example` to `.env` for local setup. Never commit `.env` (it contains Azure AD client secrets). GitHub secret scanning will reject pushes containing Azure secrets. Treat `storage/uploads/` as runtime data. Ensure `__pycache__` and `*.pyc` are in `.gitignore` before committing.
