# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

### Backend (run from repo root, `backend/` is the working directory)

```bash
# Install dependencies
pip install -r requirements.txt

# Apply database migrations (REQUIRED; run before first boot)
alembic upgrade head

# Seed initial data (roles, permissions, user levels, SuperAdmin)
python seed.py

# Run development server
uvicorn main:app --reload

# Run tests
pytest -q

# Run specific test file
pytest tests/test_file_name.py

# Run specific test class or function
pytest tests/test_file_name.py::TestClassName::test_function_name

# Lint with ruff
ruff check .

# Format with black
black .

# Check type hints
mypy backend/
```

### Frontend (run from `dms-app/` directory)

```bash
# Install dependencies
npm install

# Start development server (proxies /api to backend :8000)
npm run dev

# Build production bundle
npm run build

# Lint TypeScript/ESLint
npm run lint
```

---

## High-Level Architecture

This is a **Document Management System (DMS)** with two main components:

### Backend (`backend/`)

- **Framework**: FastAPI + SQLModel (ORM) with PostgreSQL in production
- **Auth**: JWT access + refresh tokens via `python-jose`
- **Password hashing**: bcrypt/argon2 via `passlib`
- **API structure**: REST under `/api/v1` with versioned routers
- **Middleware stack** (outermost → innermost):
  1. CORS (browser access)
  2. HTTPS enforcement
  3. Rate limiting (spec 31)
  4. Audit logging
  5. RBAC authorization
  6. Router endpoints
- **Database**: SQLModel/ORM migrations via Alembic
- **Key modules**: auth, users, documents, workflow, workflow-instances, signatures, memos, correspondence, categories, directories, storage, backups, db-backups, antivirus, company-profile, correspondence

### Frontend (`dms-app/`)

- **Framework**: React + TypeScript + Vite
- **API client**: `apiClient` from `./client` (baseURL `/api/v1`)
- **Build**: `npm run build` (tsc + vite build)
- **Styling**: Tailwind CSS via `@tailwind` directives in `index.css`

### Data Flow

```
Frontend (React/Vite) → HTTPS → CORS → Rate Limit → Audit → RBAC → API Routes → DB (PostgreSQL)
```

---

## Code Style & Conventions

### Python (backend)

- Python 3.11+, PEP8, snake_case
- Type hints for all public functions
- FastAPI endpoints must declare request/response models
- Business logic stays out of routers; use service helpers
- Use async routes when calling external APIs
- Use SQLModel / SQLAlchemy parameterized queries only
- Centralized exception handling in `core/exceptions.py`
- Structured JSON logging with correlation IDs
- Keep filenames lowercase for new modules

### TypeScript/React (frontend)

- 2-space indentation
- PascalCase components, camelCase hooks/stores
- Tailwind CSS utilities
- ESLint with React recommendations
- Type checking is part of `npm run build`

### File Organization (per AGENTS.md)

| Module | Typical Contents |
|--------|-----------------|
| `models.py` | SQLModel + read schemas |
| `schemas.py` | Write schemas (optional) |
| `service.py` | Class-based, takes `Session` |
| `router.py` | Thin — business logic in service |

---

## Spec-Driven Workflow

Features are numbered steps. Specs live in `specs/` directory (older `feature_*`/`instruction_*` files are legacy). Use `/create-spec` (`.opencode/commands/create-spec.md`) to scaffold the next one with required structure:

- Overview
- Depends on
- Routes
- Database changes
- Files to change
- Files to create
- New dependencies
- Rules for implementation
- Definition of done

Check `specs/` for the highest number before starting new work. Do not create a `plans/` directory.

---

## Known Baseline Failures

The test suite has 2 known constant failures (do not chase as regressions):

- `test_workflow.py::TestApprovalActionService::test_parallel_step_any_approve_completes`
- `test_workflow_company.py::TestSuperAdminCategoryRestrictions::test_superadmin_cannot_modify_category_ids`

Recent healthy runs: `2 failed, 686 passed`.

Before declaring tests done, target a file/class but budget ~20 min for a full run.

---

## Commands Summary

| Purpose | Command |
|---------|---------|
| Install deps (backend) | `pip install -r requirements.txt` |
| Apply migrations | `alembic upgrade head` |
| Seed data | `python seed.py` |
| Run backend dev server | `uvicorn main:app --reload` |
| Run tests | `pytest -q` |
| Lint | `ruff check .` |
| Format | `black .` |
| Install deps (frontend) | `cd dms-app && npm install` |
| Run frontend dev | `cd dms-app && npm run dev` |
| Build frontend | `cd dms-app && npm run build` |
| Lint frontend | `cd dms-app && npm run lint` |

---

## Important Notes (from AGENTS.md)

### DB / Startup Invariant

- `main.py`'s lifespan calls `create_db_and_tables()` when `DEBUG=True`, silently bypassing Alembic. It builds tables from SQLModel metadata only, so it will not apply column adds to existing tables. Production runs `DEBUG=false` + `alembic upgrade head` only.

### Enum Columns Migration Trap

- A migration's `server_default` must use the enum's `.name` (UPPERCASE), not `.value`. SQLModel maps `field: SomeStrEnum` to `sa.Enum`, which writes *and* expects the member's name. lowercase defaults survive unnoticed until something inserts relying on the default.

### Company Scoping (cross-cutting, easiest thing to break)

- `Company` is the tenancy boundary. `users`, `categories`, `correspondences` carry a `company_id` FK.
- **ADMIN** is auto-scoped to `current_user.company_id`. Client-supplied `company_id` in payload is ignored, not rejected.
- **SUPERADMIN** passes authorization guards but is denied at the service layer for mutations (403). It can only read, and needs an explicit `company_id` query param to scope.
- `Company.short_name` is the storage namespace and must match `[A-Za-z0-9_-]+`; validated on every path build.

### RBAC: Two Layers

1. `middleware/rbac.py` `ROUTE_PERMISSION_MAP` maps `(HTTP_METHOD, path_prefix)` → `PermissionAction`, matched by **longest prefix**.
2. Per-endpoint `dependencies=[Depends(require_permission(PermissionAction.X))]` in the router.

Do not invent permission verbs — the matrix is fixed at `view`, `download`, `create`, `update`, `delete`.

### Auth & User Injection

- `core/dependencies.py` provides `CurrentUser`, `AdminUser`, `AdminOnlyUser`, `SuperAdminUser`, `require_permission`.
- JWT access + refresh via `core/security.py`; `main.py` rewrites OpenAPI security to plain `HTTPBearer`.

### Audit Trail

- `AuditService.log_event()` in `audit/service.py` is the single audit sink. Opens its own `Session(engine)` so logs commit even when caller rolls back, and never raises. Call it after every significant mutation in a service. Audit records are immutable.

### Directory Navigation Access

Three tiers (do not collapse them):

- **Direct access** (`ensure_directory_access`, `ensure_category_access`): Required for ALL writes and document detail/view/download.
- **Navigation access** (`can_navigate_directory` / `ensure_directory_read_access`): Read-only traversal of a parent with ≥1 accessible descendant.
- **Category metadata** (`ensure_category_read_access`): Directory-grant users may read a category holding one of their grants.

Non-admin denials return **404, not 403** (oracle avoidance).

### Stored Path Values

- `storage_path` values are **company-relative and POSIX** (`uploads/<category_id>/<directory_id>/<file>`).
- Rows written on Windows hold backslashes, which are literal filename characters on Linux — resolver normalizes `\` → `/`.
- Always resolve through `documents/utils.py::resolve_storage_path(relative_path, company)` — never `STORAGE_ROOT / relative_path` by hand.

### Rate Limiting (spec 31)

- In-process token buckets per `(rule, client_ip)` (no Redis; single uvicorn worker).
- Rules: `auth` = 10/requests/window on `/api/v1/auth/login`, `default` = 600/requests/window on `/api/v1`.
- Skips `OPTIONS`, anything outside `/api/v1` (`/health`, `/docs`), and everything when `RATE_LIMIT_ENABLED=false`.
- Rejection = **429 + `Retry-After` + JSON `detail`**.

### Azure AD

- Company-scoped and database-driven — no global `.env` fallback.
- Config lives on `Company` (`azure_client_id`, `azure_client_secret`, `azure_tenant_id`, `azure_enabled`, `azure_default_role_name`).
- Managed via `/api/v1/companies/{id}/azure-config` (secret is write-only).
- `GET /azure/login?company_id=<id>` requires the company and validates it server-side.

### Deploy

- Production is **not** Docker: `dms-backend.service` (systemd unit, uvicorn on 127.0.0.1:8000) + `dms.conf` (nginx TLS terminating).
- `docker-compose.yml` is stale — it builds `./backend` and `./frontend`, which do not exist.
- TLS via Let's Encrypt/bootstrap with `scripts/tls/install_tls.sh`.

### Commits

- Short imperative subjects in the repo's existing style (e.g. `Implemented Reply correspondence lifecycle-v1`).
- End git commit messages with: `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- End pull request descriptions with: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`